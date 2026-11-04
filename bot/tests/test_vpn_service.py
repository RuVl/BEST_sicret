import asyncio
from types import SimpleNamespace

import httpx
from py3xui import BulkResult, BulkSkip, ClientDetails

from includes.vpn import service as vpn_service
from jobs import revoke_vpn
from tests.fakes import FakeBot, FakeL10n, FakeSessionMaker
from utils import split_message


class _RevokePanel:
    """Панель для джоба отзыва: ``broken`` - панель пропускает клиента, ``missing`` - клиента уже нет."""

    def __init__(
        self,
        broken: set[str] = frozenset(),
        missing: set[str] = frozenset(),
        error: Exception | None = None,
    ):
        self._broken = broken
        self._missing = missing
        self._error = error

    @property
    def client(self) -> "_RevokePanel":
        return self

    async def get_details(self, email: str) -> ClientDetails | None:
        if self._error is not None:
            raise self._error
        return None if email in self._missing else _details(email=email)

    async def bulk_disable(self, emails: list[str]) -> BulkResult:
        broken = [email for email in emails if email in self._broken]
        return BulkResult(skipped=[BulkSkip(email=email, reason="skipped") for email in broken])


def _subscription(n: int) -> SimpleNamespace:
    person = SimpleNamespace(telegram_id=100 + n, full_name=f"Person {n}")
    return SimpleNamespace(id=n, xui_email=f"p{n}@best-eu.org", person=person, status="active")


def _run_revoke(monkeypatch, subscriptions, panel, sessions: FakeSessionMaker) -> FakeBot:
    async def list_subscriptions_to_revoke(session):
        # Загруженные строки привязаны к сессии: её коммит сохранит и все их правки.
        for subscription in subscriptions:
            session.add(subscription)
        return subscriptions

    async def get_hr_id(session):
        return 1

    monkeypatch.setattr(revoke_vpn, "async_session", sessions)
    monkeypatch.setattr(revoke_vpn, "list_subscriptions_to_revoke", list_subscriptions_to_revoke)
    monkeypatch.setattr(revoke_vpn, "get_hr_id", get_hr_id)
    monkeypatch.setattr(revoke_vpn, "get_xui_api", lambda: panel)

    bot = FakeBot()
    asyncio.run(revoke_vpn.revoke_inactive_subscriptions(bot, FakeL10n()))
    return bot


class TestRevokeJob:
    def test_one_failure_does_not_undo_the_others(self, monkeypatch):
        # Панель отказала на p2, БД - на p3: остальные закоммичены каждый сам и уведомлены ровно по разу.
        subs = [_subscription(n) for n in range(1, 6)]
        sessions = FakeSessionMaker(fail_commit=lambda row: row.id == 3)
        panel = _RevokePanel(broken={"p2@best-eu.org"}, missing={"p5@best-eu.org"})
        bot = _run_revoke(monkeypatch, subs, panel, sessions)

        assert [row.id for row in sessions.committed] == [1, 4, 5]
        notified = [chat_id for chat_id, _ in bot.sent if chat_id != 1]
        assert notified == [101, 104]
        report = "\n".join(text for chat_id, text in bot.sent if chat_id == 1)
        assert "'revoked': 2" in report
        assert "'failed': 2" in report

    def test_notice_is_sent_only_after_commit(self, monkeypatch):
        # Уведомили, а статус не сохранился - следующей ночью человеку пришло бы второе уведомление.
        sessions = FakeSessionMaker(fail_commit=lambda row: True)
        bot = _run_revoke(monkeypatch, [_subscription(1)], _RevokePanel(), sessions)

        assert all(chat_id == 1 for chat_id, _ in bot.sent)

    def test_panel_404_is_a_failure_not_a_missing_client(self, monkeypatch):
        # Неверный XUI_BASE_URL даёт 404 на всё. Считать это «клиента нет» значило бы пометить подписку
        # отозванной, оставив ключ рабочим, и ничего не сказать в сводке.
        request = httpx.Request("GET", "https://panel/wrong/panel/api/clients/get/x")
        not_found = httpx.HTTPStatusError("404", request=request, response=httpx.Response(404, request=request))
        sessions = FakeSessionMaker()
        bot = _run_revoke(monkeypatch, [_subscription(1)], _RevokePanel(error=not_found), sessions)

        assert sessions.committed == []
        report = "\n".join(text for chat_id, text in bot.sent if chat_id == 1)
        assert "'revoked': 0" in report
        assert "'failed': 1" in report


def _details(**client) -> ClientDetails:
    base = {"email": "ivan@best-eu.org", "enable": True, "uuid": "u1", "subId": "s1"}
    return ClientDetails.model_validate({"client": base | client})


class _Panel:
    def __init__(self, clients: dict[str, ClientDetails]):
        self._clients = clients

    @property
    def client(self) -> "_Panel":
        return self

    async def get_details(self, email: str) -> ClientDetails | None:
        return self._clients.get(email)


def _resolve(monkeypatch, known_person_id: int | None, **client) -> str:
    async def get_subscription_by_email(session, email):
        return None if known_person_id is None else SimpleNamespace(person_id=known_person_id)

    monkeypatch.setattr(vpn_service, "get_subscription_by_email", get_subscription_by_email)
    person = SimpleNamespace(id=7, telegram_id=100, full_name="Иванов Иван")
    member = SimpleNamespace(best_email="ivan@best-eu.org", full_name_ru="Иванов Иван")
    panel = _Panel({"ivan@best-eu.org": _details(**client)})
    email, _ = asyncio.run(vpn_service._resolve_target(None, panel, person, member))
    return email


class TestResolveTarget:
    def test_own_subscription_is_adopted(self, monkeypatch):
        assert _resolve(monkeypatch, known_person_id=7) == "ivan@best-eu.org"

    def test_subscription_of_another_person_is_not_taken(self, monkeypatch):
        # Сменил Telegram-аккаунт или дубль почты в таблице: чужую строку не переписываем.
        assert _resolve(monkeypatch, known_person_id=8, tgId=100) == "lbg-7"

    def test_manual_client_of_same_person_is_adopted(self, monkeypatch):
        assert _resolve(monkeypatch, known_person_id=None, tgId=100, comment="Иванов Иван") == "ivan@best-eu.org"

    def test_manual_client_of_someone_else_is_not_taken(self, monkeypatch):
        assert _resolve(monkeypatch, known_person_id=None, tgId=555) == "lbg-7"


class TestPersonComment:
    def test_name_from_members_table_wins(self):
        person = SimpleNamespace(full_name="Ivan Ivanov")
        assert vpn_service.person_comment(person, SimpleNamespace(full_name_ru="Иванов Иван")) == "Иванов Иван"

    def test_falls_back_to_telegram_name(self):
        person = SimpleNamespace(full_name="Ivan Ivanov")
        assert vpn_service.person_comment(person, None) == "Ivan Ivanov"
        assert vpn_service.person_comment(person, SimpleNamespace(full_name_ru=None)) == "Ivan Ivanov"


class TestSplitMessage:
    def test_short_text_is_one_message(self):
        assert split_message("a\nb") == ["a\nb"]

    def test_splits_by_lines(self):
        text = "\n".join(["x" * 10] * 5)
        parts = split_message(text, limit=25)
        assert all(len(part) <= 25 for part in parts)
        assert "\n".join(parts) == text

    def test_long_line_is_not_cut_inside_escape(self):
        # «\.» - одна экранированная точка MarkdownV2: разрезать её нельзя.
        parts = split_message("ab\\.cd", limit=3)
        assert all(not part.endswith("\\") for part in parts)
        assert "".join(parts) == "ab\\.cd"
