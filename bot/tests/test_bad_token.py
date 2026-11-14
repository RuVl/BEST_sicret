"""Запуск с негодным токеном: подсказка и код выхода вместо трейсбэка."""

import pytest
from aiogram import Bot
from aiogram.exceptions import TelegramUnauthorizedError
from aiogram.methods import SetMyCommands

import run
from env import settings


@pytest.fixture(autouse=True)
def no_logging_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(run, "setup_logging", lambda: None)


def test_placeholder_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.telegram, "API_TOKEN", "api-key")

    with pytest.raises(SystemExit) as exit_info:
        run.start()

    assert exit_info.value.code == run.BAD_TOKEN_HELP


def test_token_rejected_by_telegram(monkeypatch: pytest.MonkeyPatch) -> None:
    closed: list[bool] = []

    async def rejected(self: Bot, *args, **kwargs) -> None:
        raise TelegramUnauthorizedError(method=SetMyCommands(commands=[]), message="Unauthorized")

    async def close(self) -> None:
        closed.append(True)

    monkeypatch.setattr(settings.telegram, "API_TOKEN", "123456:wrong-but-valid-format")
    monkeypatch.setattr(Bot, "set_my_commands", rejected)
    monkeypatch.setattr("aiogram.client.session.aiohttp.AiohttpSession.close", close)

    with pytest.raises(SystemExit) as exit_info:
        run.start()

    assert exit_info.value.code == run.BAD_TOKEN_HELP
    assert closed == [True]
