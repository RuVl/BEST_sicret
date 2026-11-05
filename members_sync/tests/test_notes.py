"""Заметка-тревога: появляется на A1, снимается сама и не трогает заметки людей."""

from sheets.notes import NoteManager

MARKER = "🤖 [sync]"
FIRST_SHEET = "Database of Members"


class FakeSpreadsheet:
    """Только то, что читает и пишет ``NoteManager``: заметки первого листа и запросы на их запись."""

    def __init__(self, notes: list[list[str]] | None = None) -> None:
        self.notes = notes or []
        self.requests: list[dict] = []

    def fetch_sheet_metadata(self, params: dict) -> dict:
        rows = [{"values": [{"note": note} for note in row]} for row in self.notes]
        return {"sheets": [{"properties": {"title": FIRST_SHEET, "sheetId": 7}, "data": [{"rowData": rows}]}]}

    def batch_update(self, body: dict) -> None:
        self.requests.extend(body["requests"])

    def written_notes(self) -> dict[tuple[int, int], str]:
        result = {}
        for request in self.requests:
            cells = request["updateCells"]
            where = cells["range"]
            result[where["startRowIndex"], where["startColumnIndex"]] = cells["rows"][0]["values"][0]["note"]
        return result


def _manager(spreadsheet: FakeSpreadsheet, enabled: bool = True) -> NoteManager:
    manager = NoteManager(spreadsheet, MARKER, enabled)
    manager.register_sheet(FIRST_SHEET)
    return manager


def test_alert_lands_on_the_first_cell():
    spreadsheet = FakeSpreadsheet()
    manager = _manager(spreadsheet)

    manager.add(FIRST_SHEET, "A1", "ВАЖНО: остановлено")
    manager.flush()

    assert spreadsheet.written_notes() == {(0, 0): f"{MARKER} ВАЖНО: остановлено"}


def test_alert_disappears_after_a_clean_run():
    spreadsheet = FakeSpreadsheet([[f"{MARKER} ВАЖНО: остановлено"]])

    _manager(spreadsheet).flush()

    assert spreadsheet.written_notes() == {(0, 0): ""}


def test_clean_run_keeps_human_notes():
    spreadsheet = FakeSpreadsheet([["заметка человека"]])

    _manager(spreadsheet).flush()

    assert spreadsheet.requests == []


def test_disabled_notes_write_nothing():
    spreadsheet = FakeSpreadsheet()
    manager = _manager(spreadsheet, enabled=False)

    manager.add(FIRST_SHEET, "A1", "ВАЖНО: остановлено")
    manager.flush()

    assert spreadsheet.requests == []
