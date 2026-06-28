"""Запись/снятие заметок об ошибках в ячейках Google-таблицы.

Все заметки сервиса помечены маркером (``SHEET_NOTE_MARKER``). При каждом прогоне:
- свои устаревшие заметки (ошибки, которых больше нет) снимаются;
- человеческие заметки (без маркера) не трогаются;
- актуальные ошибки записываются заново (идемпотентно).

Один батч-запрос на всю таблицу.
"""

import time

import structlog
from gspread import Spreadsheet
from gspread.utils import a1_to_rowcol, absolute_range_name

log = structlog.get_logger("members_sync.notes")


class NoteManager:
    def __init__(self, spreadsheet: Spreadsheet, marker: str, enabled: bool) -> None:
        self.spreadsheet = spreadsheet
        self.marker = marker
        self.enabled = enabled
        self._sheets: set[str] = set()
        self._pending: dict[str, dict[str, list[str]]] = {}
        self.written = 0
        self.cleared = 0

    def register_sheet(self, title: str) -> None:
        """Отметить лист как обработанный (чтобы снимать с него устаревшие заметки)."""
        self._sheets.add(title)
        self._pending.setdefault(title, {})

    def add(self, sheet_title: str, a1: str, text: str) -> None:
        self._sheets.add(sheet_title)
        cell_map = self._pending.setdefault(sheet_title, {})
        cell_map.setdefault(a1, []).append(text)

    def _note_request(self, sheet_id: int, row0: int, col0: int, text: str) -> dict:
        return {
            "updateCells": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": row0,
                    "endRowIndex": row0 + 1,
                    "startColumnIndex": col0,
                    "endColumnIndex": col0 + 1,
                },
                "rows": [{"values": [{"note": text}]}],
                "fields": "note",
            }
        }

    def _fetch_sheets_meta(self, titles: set[str]) -> dict[str, tuple[int, list[list[str]]]]:
        """{title: (sheet_id, заметки)} одним запросом метаданных по всем нужным листам.

        Заменяет ``worksheet.get_notes()`` на каждый лист — это были отдельные round-trip'ы.
        """
        params = {
            "fields": "sheets.properties.title,sheets.properties.sheetId,sheets.data.rowData.values.note",
            "ranges": [absolute_range_name(t) for t in titles],
        }
        try:
            response = self.spreadsheet.fetch_sheet_metadata(params)
        except Exception as exc:  # noqa: BLE001
            log.warning("Не удалось прочитать метаданные листов для заметок", error=str(exc))
            return {}

        result: dict[str, tuple[int, list[list[str]]]] = {}
        for sheet in response.get("sheets", []):
            props = sheet.get("properties", {})
            title = props.get("title")
            if title is None:
                continue
            row_data = (sheet.get("data") or [{}])[0].get("rowData", [])
            notes = [[cell.get("note", "") for cell in row.get("values", [])] for row in row_data]
            result[title] = (props.get("sheetId", 0), notes)
        return result

    def flush(self) -> None:
        if not self.enabled:
            pending = sum(len(c) for c in self._pending.values())
            log.info("Заметки отключены (WRITE_SHEET_NOTES=false)", pending=pending)
            return
        if not self._sheets:
            log.info("Заметки обновлены", written=0, cleared=0, elapsed_s=0.0)
            return

        start = time.perf_counter()
        meta = self._fetch_sheets_meta(self._sheets)
        requests: list[dict] = []

        for title in self._sheets:
            info = meta.get(title)
            if info is None:
                log.warning("Лист не найден для заметок", sheet=title)
                continue
            sheet_id, existing = info

            pending_cells: dict[tuple[int, int], str] = {}
            for a1, texts in self._pending.get(title, {}).items():
                try:
                    row1, col1 = a1_to_rowcol(a1)
                except Exception:  # noqa: BLE001
                    continue
                body = "\n".join(texts)
                pending_cells[(row1 - 1, col1 - 1)] = f"{self.marker} {body}"

            # Снимаем свои устаревшие заметки.
            for r, row_notes in enumerate(existing):
                for c, note in enumerate(row_notes):
                    if note and note.startswith(self.marker) and (r, c) not in pending_cells:
                        requests.append(self._note_request(sheet_id, r, c, ""))
                        self.cleared += 1

            # Пишем актуальные.
            for (r, c), text in pending_cells.items():
                requests.append(self._note_request(sheet_id, r, c, text))
                self.written += 1

        if requests:
            self.spreadsheet.batch_update({"requests": requests})
        log.info(
            "Заметки обновлены",
            written=self.written,
            cleared=self.cleared,
            elapsed_s=round(time.perf_counter() - start, 2),
        )
