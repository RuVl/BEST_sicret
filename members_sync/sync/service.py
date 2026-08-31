"""Оркестратор одного прогона синхронизации."""

import time
from datetime import UTC, datetime

import structlog
from gspread.utils import absolute_range_name

from database.main import async_session
from database.methods.member import deactivate_missing, link_unlinked_persons, upsert_member
from env import SyncKeys
from parsing import fields as F
from parsing.issues import IssueCollector
from parsing.member_builder import ParsedMember, build
from sheets.client import open_spreadsheet
from sheets.column_mapper import resolve_columns
from sheets.notes import NoteManager
from sheets.record_reader import iterate_records
from sheets.spec import SheetSpec, spec_for_title
from sync.report import RunReport, SheetStat, dump_members, write_report

log = structlog.get_logger("members_sync.service")


def _fetch_sheet_values(spreadsheet) -> list[tuple[str, SheetSpec, list[list[str]]]]:
    """Одним батч-запросом забрать значения всех листов, под которые есть раскладка.

    Раньше на каждый лист шёл отдельный ``get_all_values()`` — N сетевых round-trip'ов,
    что упиралось в латентность и rate-limit Google API. Теперь — один ``values_batch_get``.
    """
    targets: list[tuple[str, SheetSpec]] = []
    for worksheet in spreadsheet.worksheets():
        spec = spec_for_title(worksheet.title)
        if spec is None:
            log.debug("Лист пропущен (нет раскладки)", sheet=worksheet.title)
            continue
        targets.append((worksheet.title, spec))

    if not targets:
        return []

    ranges = [absolute_range_name(title) for title, _ in targets]
    response = spreadsheet.values_batch_get(ranges)
    value_ranges = response.get("valueRanges", [])  # порядок совпадает с порядком ranges

    result: list[tuple[str, SheetSpec, list[list[str]]]] = []
    for (title, spec), value_range in zip(targets, value_ranges, strict=False):
        result.append((title, spec, value_range.get("values", [])))
    return result


def _precedence(member: ParsedMember) -> int:
    """Вес записи при дедупе: у ParsedMember членство уже разложено по флагам."""
    membership = F.Membership(
        member.membership_category or "",
        is_active=member.is_active,
        is_excluded=member.is_excluded,
    )
    return F.membership_precedence(membership)


def _parse_sheets(
    sheet_values: list[tuple[str, SheetSpec, list[list[str]]]],
    issues: IssueCollector,
    notes: NoteManager,
    report: RunReport,
):
    """Разобрать заранее загруженные листы и собрать ParsedMember с дедупом по identity_key."""
    parsed: dict[str, ParsedMember] = {}

    for title, spec, values in sheet_values:
        notes.register_sheet(title)
        column_index = resolve_columns(values, spec, title, issues)

        count = 0
        for record in iterate_records(values, spec, column_index, title):
            member = build(record, spec, issues)
            if member is None:
                continue
            count += 1

            existing = parsed.get(member.identity_key)
            if existing is None:
                parsed[member.identity_key] = member
            elif _precedence(member) > _precedence(existing):
                parsed[member.identity_key] = member
                report.duplicates += 1
                issues.add(
                    title,
                    "duplicate",
                    f"дубликат между листами: также на {existing.source_sheet} (строка {existing.source_row_start})",
                )
            else:
                report.duplicates += 1
                issues.add(
                    title,
                    "duplicate",
                    f"дубликат между листами: приоритетная запись на "
                    f"{existing.source_sheet} (строка {existing.source_row_start})",
                )

        report.sheets.append(SheetStat(title=title, layout=spec.layout, records=count))
        log.info("Лист обработан", sheet=title, layout=spec.layout, records=count)

    return parsed


async def run_sync(dry_run: bool = False) -> RunReport:
    """Один прогон синхронизации.

    ``dry_run=True`` — парсим боевые данные из Google Sheets и пишем дамп в JSON,
    но БД не трогаем и заметки в таблицу не пишем (для проверки парсинга вживую).
    """
    now = datetime.now(UTC)
    report = RunReport(started_at=now)
    issues = IssueCollector()

    try:
        t = time.perf_counter()
        spreadsheet = open_spreadsheet()
        log.info("Таблица открыта", elapsed_s=round(time.perf_counter() - t, 2))
        # В dry-run заметки в таблицу не пишем — только читаем и дампим JSON.
        notes = NoteManager(spreadsheet, SyncKeys.SHEET_NOTE_MARKER, SyncKeys.WRITE_SHEET_NOTES and not dry_run)

        t = time.perf_counter()
        sheet_values = _fetch_sheet_values(spreadsheet)
        log.info("Значения листов загружены", sheets=len(sheet_values), elapsed_s=round(time.perf_counter() - t, 2))

        parsed = _parse_sheets(sheet_values, issues, notes, report)
        members = list(parsed.values())
        report.total_parsed = len(members)
        for member in members:
            report.by_category[member.membership_category or "—"] += 1
            report.active += member.is_active
            report.excluded += member.is_excluded

        # Запись в БД (в dry-run пропускаем — только дамп в JSON).
        if dry_run:
            log.info("dry-run: запись в БД и заметки в таблицу пропущены")
        else:
            async with async_session() as session:
                for member in members:
                    result = await upsert_member(session, member, now)
                    if result == "inserted":
                        report.inserted += 1
                    else:
                        report.updated += 1
                report.deactivated = await deactivate_missing(session, parsed.keys(), now)
                report.linked_persons = await link_unlinked_persons(session)
                await session.commit()

            log.info(
                "БД синхронизирована",
                inserted=report.inserted,
                updated=report.updated,
                deactivated=report.deactivated,
                linked_persons=report.linked_persons,
            )

        # Заметки об ошибках в таблице.
        for issue in issues:
            if issue.a1:
                notes.add(issue.sheet, issue.a1, issue.message)
        notes.flush()
        report.notes_enabled = notes.enabled
        report.notes_written = notes.written
        report.notes_cleared = notes.cleared

        dump_members(members, SyncKeys.DUMP_JSON_PATH)

    except Exception as exc:  # noqa: BLE001 - один прогон не должен ронять планировщик
        report.error = f"{type(exc).__name__}: {exc}"
        log.exception("Прогон синхронизации завершился ошибкой")

    finally:
        report.finished_at = datetime.now(UTC)
        report.issues = list(issues)
        write_report(report, SyncKeys.SYNC_REPORT_PATH)

    # Лог итоговых проблем (попадут также в markdown-лог предупреждений).
    for issue in issues.errors:
        log.error(issue.render())
    for issue in issues.warnings:
        log.warning(issue.render())

    log.info(
        "Прогон завершён",
        parsed=report.total_parsed,
        errors=len(issues.errors),
        warnings=len(issues.warnings),
        duration_s=round(report.duration_s, 1),
    )
    return report
