"""Сопоставление заголовков листа с каноническими колонками."""

from gspread.utils import rowcol_to_a1

from parsing.issues import IssueCollector
from parsing.normalizers import normalize_header
from sheets.spec import SheetSpec


def resolve_columns(
    values: list[list[str]],
    spec: SheetSpec,
    sheet_title: str,
    issues: IssueCollector,
) -> dict[str, int]:
    """Вернуть отображение ``canonical_column -> column_index``.

    Сначала пытаемся найти колонку по алиасам заголовка; если не нашли —
    используем запасной индекс (с предупреждением). Обязательные колонки, которые
    не удалось определить вовсе, дают ошибку.
    """
    header = values[spec.header_row] if spec.header_row < len(values) else []
    norm = [normalize_header(h) for h in header]

    mapping: dict[str, int] = {}
    used: set[int] = set()

    for col in spec.columns:
        found: int | None = None
        for alias in col.aliases:
            na = normalize_header(alias)
            for idx, h in enumerate(norm):
                if idx in used or not h:
                    continue
                if na == h or na in h:
                    found = idx
                    break
            if found is not None:
                break

        if found is None and col.fallback_index is not None:
            found = col.fallback_index
            a1 = rowcol_to_a1(spec.header_row + 1, found + 1)
            issues.add(
                sheet_title,
                col.name,
                f"заголовок не найден, использован запасной индекс (колонка {found + 1})",
                a1,
            )

        if found is not None:
            mapping[col.name] = found
            used.add(found)
        elif col.required:
            issues.add(
                sheet_title,
                col.name,
                "обязательная колонка не найдена в заголовке",
                level="error",
            )

    return mapping
