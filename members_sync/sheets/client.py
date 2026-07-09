import gspread

from env import GoogleKeys


def open_spreadsheet() -> gspread.Spreadsheet:
    """Открыть таблицу по ключу через сервис-аккаунт."""
    gc = gspread.service_account(filename=GoogleKeys.API_CREDENTIALS_FILE)
    return gc.open_by_key(GoogleKeys.SPREADSHEET_KEY)
