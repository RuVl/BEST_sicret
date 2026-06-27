"""Оркестратор одного прогона синхронизации."""

from datetime import UTC, datetime

import structlog

from database.main import async_session
from database.methods.member import deactivate_missing, upsert_member
from env import SyncKeys
from parsing import fields as F
from parsing.issues import IssueCollector
from parsing.member_builder import ParsedMember, build
from sheets.client import open_spreadsheet
from sheets.column_mapper import resolve_columns
from sheets.notes import NoteManager
from sheets.record_reader import iterate_records
from sheets.spec import spec_for_title
from sync.report import RunReport, SheetStat, dump_members, write_report

log = structlog.get_logger("members_sync.service")


def _parse_sheets(spreadsheet, issues: IssueCollector, notes: NoteManager, report: RunReport):
    """Прочитать все подходящие листы и собрать ParsedMember с дедупом по identity_key."""
    parsed: dict[str, ParsedMember] = {}

    for worksheet in spreadsheet.worksheets():
        title = worksheet.title
        spec = spec_for_title(title)
        if spec is None:
            log.debug("Лист пропущен (нет раскладки)", sheet=title)
            continue

        notes.register_sheet(title)
        values = worksheet.get_all_values()
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
            elif F.status_precedence(member.membership_status) > F.status_precedence(existing.membership_status):
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


async def run_sync() -> RunReport:
    now = datetime.now(UTC)
    report = RunReport(started_at=now)
    issues = IssueCollector()

    try:
        spreadsheet = open_spreadsheet()
        notes = NoteManager(spreadsheet, SyncKeys.SHEET_NOTE_MARKER, SyncKeys.WRITE_SHEET_NOTES)

        parsed = _parse_sheets(spreadsheet, issues, notes, report)
        members = list(parsed.values())
        report.total_parsed = len(members)
        for member in members:
            report.by_status[member.membership_status or "—"] += 1
            report.by_category[member.membership_category or "—"] += 1

        # Запись в БД.
        async with async_session() as session:
            for member in members:
                result = await upsert_member(session, member, now)
                if result == "inserted":
                    report.inserted += 1
                else:
                    report.updated += 1
            report.deactivated = await deactivate_missing(session, parsed.keys(), now)
            await session.commit()

        log.info(
            "БД синхронизирована",
            inserted=report.inserted,
            updated=report.updated,
            deactivated=report.deactivated,
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
