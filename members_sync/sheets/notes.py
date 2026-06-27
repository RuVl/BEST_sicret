"""Запись/снятие заметок об ошибках в ячейках Google-таблицы.

Все заметки сервиса помечены маркером (``SHEET_NOTE_MARKER``). При каждом прогоне:
- свои устаревшие заметки (ошибки, которых больше нет) снимаются;
- человеческие заметки (без маркера) не трогаются;
- актуальные ошибки записываются заново (идемпотентно).

Один батч-запрос на всю таблицу.
"""

import structlog
from gspread import Spreadsheet
from gspread.utils import a1_to_rowcol

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

    def flush(self) -> None:
        if not self.enabled:
            pending = sum(len(c) for c in self._pending.values())
            log.info("Заметки отключены (WRITE_SHEET_NOTES=false)", pending=pending)
            return

        requests: list[dict] = []

        for title in self._sheets:
            try:
                worksheet = self.spreadsheet.worksheet(title)
            except Exception as exc:  # noqa: BLE001
                log.warning("Лист не найден для заметок", sheet=title, error=str(exc))
                continue

            sheet_id = worksheet.id
            pending_cells: dict[tuple[int, int], str] = {}
            for a1, texts in self._pending.get(title, {}).items():
                try:
                    row1, col1 = a1_to_rowcol(a1)
                except Exception:  # noqa: BLE001
                    continue
                body = "\n".join(texts)
                pending_cells[(row1 - 1, col1 - 1)] = f"{self.marker} {body}"

            # Снимаем свои устаревшие заметки.
            try:
                existing = worksheet.get_notes()
            except Exception as exc:  # noqa: BLE001
                log.warning("Не удалось прочитать заметки", sheet=title, error=str(exc))
                existing = []
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
        log.info("Заметки обновлены", written=self.written, cleared=self.cleared)
