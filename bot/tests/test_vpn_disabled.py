"""Окно VPN без настроенной панели: в панель не ходим и выпустить ничего не предлагаем."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest
from best_db.models import LbgMember, Person

from dialogs.user import vpn
from env import settings
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY


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


@asynccontextmanager
async def no_session():
    yield None


def _no_panel():
    raise AssertionError("без настроек в панель не ходим")


@pytest.fixture
def disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    async def person(session, telegram_id):
        return Person(id=1, telegram_id=telegram_id, lbg_member=LbgMember())

    async def subscription(session, person_id):
        return SimpleNamespace(xui_email="old@example.org", status="active")

    async def access(session, person_id):
        return None

    monkeypatch.setattr(settings.xui, "BASE_URL", "")
    monkeypatch.setattr(settings.xui, "API_TOKEN", "")
    monkeypatch.setattr(vpn, "async_session", no_session)
    monkeypatch.setattr(vpn, "get_person_with_member", person)
    monkeypatch.setattr(vpn, "get_subscription_by_person", subscription)
    monkeypatch.setattr(vpn, "get_access_by_person", access)
    monkeypatch.setattr(vpn, "get_xui_api", _no_panel)


@pytest.mark.usefixtures("disabled")
def test_window_says_disabled_and_offers_nothing() -> None:
    manager = SimpleNamespace(event=SimpleNamespace(from_user=SimpleNamespace(id=1)))

    data = asyncio.run(vpn.get_vpn_data(manager, FakeL10n(), FakeLog()))

    assert data == {
        "is_allowed": True,
        "has_subscription": False,
        "can_issue": False,
        "can_restore": False,
        "awg_allowed": False,
        "text": "vpn-not-configured",
    }


@pytest.mark.usefixtures("disabled")
def test_stale_issue_button_gets_alert() -> None:
    clb = FakeCallback()
    manager = SimpleNamespace(middleware_data={L10N_FORMAT_KEY: FakeL10n(), LOGGING_KEY: FakeLog()})

    asyncio.run(vpn.on_issue(clb, SimpleNamespace(widget_id="issue_vpn"), manager))

    assert clb.answers == [("vpn-not-configured-alert", True)]
