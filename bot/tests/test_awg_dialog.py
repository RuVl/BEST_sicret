"""Хэндлеры окон AmneziaWG без Telegram и БД: сессия и загрузка доступа подменены."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

from dialogs.user import vpn_awg
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from state_machines.vpn import ViewVpnSubscription


class FakeL10n:
    def format_value(self, key, args=None):
        return key


class FakeLog:
    async def aerror(self, *args, **kwargs):
        pass


class FakeCallback:
    def __init__(self) -> None:
        self.from_user = SimpleNamespace(id=1)
        self.answers: list[tuple[str | None, bool]] = []

    async def answer(self, text=None, show_alert=False):
        self.answers.append((text, show_alert))


class FakeManager:
    def __init__(self, dialog_data: dict) -> None:
        self.dialog_data = dialog_data
        self.middleware_data = {L10N_FORMAT_KEY: FakeL10n(), LOGGING_KEY: FakeLog()}
        self.state = None

    async def switch_to(self, state, show_mode=None):
        self.state = state


@asynccontextmanager
async def no_session():
    yield None


def test_delete_with_closed_access_says_denied(monkeypatch):
    removed = []

    async def closed(session, telegram_id):
        return None

    async def remove_device(*args):
        removed.append(args)

    monkeypatch.setattr(vpn_awg, "async_session", no_session)
    monkeypatch.setattr(vpn_awg, "_load_access", closed)
    monkeypatch.setattr(vpn_awg, "remove_device", remove_device)

    clb = FakeCallback()
    manager = FakeManager({vpn_awg._DEVICE: 2})
    asyncio.run(vpn_awg.on_delete_confirmed(clb, None, manager))

    assert clb.answers == [("vpn-awg-denied-alert", True)]
    assert removed == []
    assert manager.state == ViewVpnSubscription.AWG
