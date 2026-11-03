import asyncio
from types import SimpleNamespace

import pytest

from includes.vpn import ClientDetails, XuiClient, XuiError
from includes.vpn import service as vpn_service
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
