import asyncio
from types import SimpleNamespace

import pytest

from includes.vpn import ClientDetails, XuiClient, XuiClientNotFoundError, XuiError
from includes.vpn import service as vpn_service
from jobs import revoke_vpn
from tests.fakes import FakeBot, FakeL10n, FakeSessionMaker
from utils import split_message


class _HangingSession:
    """aiohttp-сессия, у которой истёк общий таймаут: aiohttp бросает голый TimeoutError."""

    closed = False

    def request(self, *args, **kwargs):
        raise TimeoutError


class TestPanelTimeout:
    def test_total_timeout_is_a_panel_error(self):
        # Иначе исключение пролетает мимо except XuiError в джобах и диалогах.
        client = XuiClient("https://panel", "token", "https://sub")
        client._session = _HangingSession()

        with pytest.raises(XuiError, match="не ответила"):
            asyncio.run(client.get_client_details("ivan@best-eu.org"))


class _CannedPanel(XuiClient):
    """Клиент панели, у которого вместо сети - заранее заготовленные ``obj`` по префиксу пути."""

    def __init__(self, responses: dict[str, object]):
        super().__init__("https://panel", "token", "https://sub")
        self._responses = responses
        self.requests: list[tuple[str, object]] = []

    async def _request(self, method, path, json=None):
        self.requests.append((path, json))
        for prefix, obj in self._responses.items():
            if path.startswith(prefix):
                return obj
        raise AssertionError(f"неожиданный запрос {path}")


_CLIENT = {"email": "ivan@best-eu.org", "uuid": "u1", "subId": "s1", "privateKey": "secret-key"}


class TestPanelResponseValidation:
    @pytest.mark.parametrize(
        "obj",
        [
            {"client": _CLIENT, "inboundIds": [3], "tunnelAllowedIPs": {"3": None}},
            {"client": _CLIENT, "inboundIds": "3"},
            {"client": "не объект"},
            ["не", "объект"],
        ],
    )
    def test_malformed_client_is_a_panel_error(self, obj):
        # Иначе pydantic.ValidationError пролетает мимо except XuiError/AwgError в диалогах и джобах.
        panel = _CannedPanel({"/clients/get/": obj})

        with pytest.raises(XuiError, match="не по схеме"):
            asyncio.run(panel.get_client_details("ivan@best-eu.org"))

    def test_error_does_not_leak_client_secrets(self):
        panel = _CannedPanel({"/clients/get/": {"client": _CLIENT, "inboundIds": [3], "tunnelAllowedIPs": {"3": None}}})

        with pytest.raises(XuiError) as caught:
            asyncio.run(panel.get_client_details("ivan@best-eu.org"))

        assert "secret-key" not in str(caught.value)

    def test_null_tunnel_addresses_are_tolerated(self):
        panel = _CannedPanel({"/clients/get/": {"client": _CLIENT, "inboundIds": [3], "tunnelAllowedIPs": None}})

        details = asyncio.run(panel.get_client_details("ivan@best-eu.org"))

        assert details is not None
        assert details.tunnel_allowed_ips == {}

    def test_malformed_traffic_is_a_panel_error(self):
        panel = _CannedPanel({"/clients/traffic/": {"up": "много"}})

        with pytest.raises(XuiError, match="не по схеме"):
            asyncio.run(panel.get_traffic("ivan@best-eu.org"))


class TestBulkSetEnabled:
    def test_skipped_emails_are_an_error(self):
        # 3x-ui на per-email провал отвечает success=true и перечисляет пропущенных в skipped.
        skipped = [{"email": "b@best-eu.org", "reason": "traffic writer queue full"}]
        panel = _CannedPanel({"/clients/bulkDisable": {"changed": 1, "skipped": skipped}})

        with pytest.raises(XuiError, match=r"b@best-eu\.org \(traffic writer queue full\)"):
            asyncio.run(panel.set_enabled_many(["a@best-eu.org", "b@best-eu.org"], False))

    @pytest.mark.parametrize(
        "obj", [{"changed": 2}, {"changed": 2, "skipped": None}, {"changed": 2, "skipped": []}, None]
    )
    def test_nothing_skipped_is_success(self, obj):
        panel = _CannedPanel({"/clients/bulkEnable": obj})

        asyncio.run(panel.set_enabled_many(["a@best-eu.org", "b@best-eu.org"], True))

        assert panel.requests == [("/clients/bulkEnable", {"emails": ["a@best-eu.org", "b@best-eu.org"]})]

    def test_skipped_single_client_is_an_error(self):
        panel = _CannedPanel(
            {
                "/clients/get/": {"client": _CLIENT, "inboundIds": [1]},
                "/clients/bulkDisable": {"changed": 0, "skipped": [{"email": "ivan@best-eu.org", "reason": "x"}]},
            }
        )

        with pytest.raises(XuiError):
            asyncio.run(panel.set_enabled("ivan@best-eu.org", False))


class _RevokePanel:
    """Панель для джоба отзыва: ``broken`` - отключение падает, ``missing`` - клиента уже нет."""

    def __init__(self, broken: set[str] = frozenset(), missing: set[str] = frozenset()):
        self._broken = broken
        self._missing = missing

    async def set_enabled(self, email: str, enabled: bool) -> None:
        if email in self._missing:
            raise XuiClientNotFoundError(email)
        if email in self._broken:
            raise XuiError("skipped")


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
    monkeypatch.setattr(revoke_vpn, "get_xui_client", lambda: panel)

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


def _details(**client) -> ClientDetails:
    return ClientDetails.model_validate({"client": {"email": "ivan@best-eu.org", "uuid": "u1", "subId": "s1"} | client})


class _Panel:
    def __init__(self, clients: dict[str, ClientDetails]):
        self._clients = clients

    async def get_client_details(self, email: str) -> ClientDetails | None:
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
