"""Открытие таблицы: без ключа понятная ошибка, а не ответ Google API."""

import gspread
import pytest

from sheets import client


def test_empty_key_stops_before_google(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_google(**kwargs):
        raise AssertionError("без ключа в Google не ходим")

    monkeypatch.setattr(client.GoogleKeys, "SPREADSHEET_KEY", "")
    monkeypatch.setattr(gspread, "service_account", no_google)

    with pytest.raises(ValueError, match="SPREADSHEET_KEY"):
        client.open_spreadsheet()
