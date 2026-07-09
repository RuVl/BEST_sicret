"""Отчёт о прогоне синхронизации (markdown) + отладочный дамп JSON."""

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from parsing.issues import ParseIssue
from parsing.member_builder import ParsedMember


@dataclass
class SheetStat:
    title: str
    layout: str
    records: int


@dataclass
class RunReport:
    started_at: datetime
    finished_at: datetime | None = None
    sheets: list[SheetStat] = field(default_factory=list)
    total_parsed: int = 0
    duplicates: int = 0
    by_status: Counter = field(default_factory=Counter)
    by_category: Counter = field(default_factory=Counter)
    inserted: int = 0
    updated: int = 0
    deactivated: int = 0
    linked_persons: int = 0
    notes_enabled: bool = False
    notes_written: int = 0
    notes_cleared: int = 0
    issues: list[ParseIssue] = field(default_factory=list)
    error: str | None = None

    @property
    def duration_s(self) -> float:
        end = self.finished_at or datetime.now(self.started_at.tzinfo)
        return (end - self.started_at).total_seconds()


def _md_table(headers: list[str], rows: list[list[str]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join("---" for _ in headers) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(out)


def write_report(report: RunReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    errors = [i for i in report.issues if i.level == "error"]
    warnings = [i for i in report.issues if i.level == "warning"]

    lines: list[str] = [
        "# members_sync — отчёт о последнем прогоне\n",
        f"- **Старт:** {report.started_at:%Y-%m-%d %H:%M:%S}",
        f"- **Длительность:** {report.duration_s:.1f} c",
    ]
    if report.error:
        lines.append(f"- **СТАТУС: ОШИБКА** — {report.error}")
    else:
        lines.append("- **Статус:** успешно")
    lines.append("")

    lines.append("## Листы\n")
    lines.append(
        _md_table(
            ["Лист", "Раскладка", "Записей"],
            [[s.title, s.layout, s.records] for s in report.sheets] or [["—", "—", 0]],
        )
    )
    lines.append("")

    lines.append("## Синхронизация\n")
    lines.append(
        _md_table(
            ["Распознано", "Добавлено", "Обновлено", "Деактивировано", "Связано Person", "Дубликатов"],
            [
                [
                    report.total_parsed,
                    report.inserted,
                    report.updated,
                    report.deactivated,
                    report.linked_persons,
                    report.duplicates,
                ]
            ],
        )
    )
    lines.append("")

    lines.append("## По статусам\n")
    lines.append(
        _md_table(
            ["Статус", "Кол-во"],
            [[k, v] for k, v in sorted(report.by_status.items())] or [["—", 0]],
        )
    )
    lines.append("")
    lines.append("## По категориям\n")
    lines.append(
        _md_table(
            ["Категория", "Кол-во"],
            [[k, v] for k, v in sorted(report.by_category.items())] or [["—", 0]],
        )
    )
    lines.append("")

    note_state = "включены" if report.notes_enabled else "отключены"
    lines.append(
        f"## Заметки в таблице ({note_state})\n\n"
        f"- Записано: {report.notes_written}\n- Снято устаревших: {report.notes_cleared}\n"
    )

    lines.append(f"## Ошибки ({len(errors)})\n")
    for issue in errors:
        lines.append(f"- {issue.render()}")
    lines.append("")
    lines.append(f"## Предупреждения ({len(warnings)})\n")
    for issue in warnings:
        lines.append(f"- {issue.render()}")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")


def dump_members(members: list[ParsedMember], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [asdict(m) for m in members]
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
