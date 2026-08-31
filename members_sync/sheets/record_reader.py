"""Сборка записей-участников из плоского списка строк листа.

Один участник = до двух физических строк. Основная строка определяется по
непустому номеру в колонке № (устойчивый признак). Между записями отслеживаются
строки-секции (BOARD, ALUMNI, …). Конец данных — несколько пустых строк подряд.
"""

from collections.abc import Iterator
from dataclasses import dataclass

from gspread.utils import rowcol_to_a1

from parsing import fields as F
from sheets.spec import SheetSpec

_EMPTY_RUN_END = 3


def _cell(row: list[str], idx: int | None) -> str:
    if idx is None or idx < 0 or idx >= len(row):
        return ""
    return (row[idx] or "").strip()


def _is_empty(row: list[str]) -> bool:
    return all(not (c or "").strip() for c in row)


def _nonempty_count(row: list[str]) -> int:
    return sum(1 for c in row if (c or "").strip())


@dataclass
class RawRecord:
    sheet_title: str
    section: str | None
    primary: list[str]
    secondary: list[str] | None
    primary_row: int  # 1-based номер строки в листе
    secondary_row: int | None
    column_index: dict[str, int]

    def raw_pair(self, column: str) -> tuple[str, str]:
        idx = self.column_index.get(column)
        p = _cell(self.primary, idx)
        s = _cell(self.secondary, idx) if self.secondary is not None else ""
        return p, s

    def a1(self, column: str, which: str = "primary") -> str | None:
        idx = self.column_index.get(column)
        if idx is None:
            return None
        row = self.primary_row if which == "primary" else self.secondary_row
        if row is None:
            return None
        return rowcol_to_a1(row, idx + 1)

    def snapshot(self) -> dict:
        """Полный сырой слепок: значения всех сопоставленных колонок + метаданные."""
        cells = {}
        for name in self.column_index:
            p, s = self.raw_pair(name)
            if p or s:
                cells[name] = {"p": p, "s": s}
        return {
            "sheet": self.sheet_title,
            "section": self.section,
            "rows": [self.primary_row, self.secondary_row],
            "cells": cells,
        }


def _is_section(row: list[str], name_idx: int | None, num_idx: int) -> bool:
    return not _cell(row, num_idx) and bool(_cell(row, name_idx)) and _nonempty_count(row) == 1


def _looks_like_stats(row: list[str]) -> bool:
    return any("statistic" in (c or "").lower() for c in row)


def iterate_records(
    values: list[list[str]],
    spec: SheetSpec,
    column_index: dict[str, int],
    sheet_title: str,
) -> Iterator[RawRecord]:
    name_idx = column_index.get(F.NAME)
    num_idx = spec.number_col

    section: str | None = None
    empty_run = 0
    i = spec.header_row + 1
    n = len(values)

    while i < n:
        row = values[i]

        if _is_empty(row):
            empty_run += 1
            if empty_run >= _EMPTY_RUN_END:
                break
            i += 1
            continue
        empty_run = 0

        if _looks_like_stats(row):
            break

        if _cell(row, num_idx).isdigit():
            secondary = None
            secondary_row = None
            if i + 1 < n:
                nxt = values[i + 1]
                # Каждый участник = ровно 2 строки: строку сразу за пронумерованной
                # основной забираем как вторичную безусловно (даже если в ней только
                # имя транслитом — заголовок секции не стоит вплотную за участником).
                if not _is_empty(nxt) and not _cell(nxt, num_idx).isdigit() and not _looks_like_stats(nxt):
                    secondary = nxt
                    secondary_row = i + 2  # 1-based
            yield RawRecord(
                sheet_title=sheet_title,
                section=section,
                primary=row,
                secondary=secondary,
                primary_row=i + 1,
                secondary_row=secondary_row,
                column_index=column_index,
            )
            i += 2 if secondary is not None else 1
            continue

        if _is_section(row, name_idx, num_idx):
            section = _cell(row, name_idx)
            i += 1
            continue

        # Прочая строка (хвостовая статистика/мусор) — пропускаем.
        i += 1
