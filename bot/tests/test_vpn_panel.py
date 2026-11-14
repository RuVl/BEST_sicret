"""Решения бота при работе с панелью 3x-ui. py3xui подменён целиком: разбор ответов панели проверяет сама библиотека."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from py3xui import BulkResult, BulkSkip, Client, ClientDetails, ClientTraffic, XuiApiError
from pydantic import ValidationError

from env import settings
from includes.awg.client import AwgClient
from includes.awg.exceptions import AwgError
from includes.vpn import panel_error_text, set_clients_enabled
from includes.vpn import service as vpn_service
from tests.fakes import fake_panel_api

PERSON = SimpleNamespace(id=7, telegram_id=100, full_name="Ivan Ivanov")
MEMBER = SimpleNamespace(best_email="ivan@best-eu.org", full_name_ru="Иванов Иван")


def _skipped(email: str, reason: str) -> BulkResult:
    return BulkResult(skipped=[BulkSkip(email=email, reason=reason)])


class TestPanelErrorText:
    def test_validation_error_does_not_leak_secrets(self):
        # email обязателен: ошибка «missing» несёт весь объект клиента вместе с ключами.
        with pytest.raises(ValidationError) as caught:
            ClientDetails.model_validate({"client": {"enable": True, "privateKey": "secret-key"}})

        text = panel_error_text(caught.value)

        assert "не по схеме" in text
        assert "secret-key" not in text

    def test_timeout_has_text(self):
        # str(httpx.ReadTimeout("")) пуст: в сводке HR осталось бы «email: ».
        assert panel_error_text(httpx.ReadTimeout("")) == "ReadTimeout"


class TestSetClientsEnabled:
    @pytest.mark.parametrize(
        ("enabled", "called", "other"),
        [(True, "bulk_enable", "bulk_disable"), (False, "bulk_disable", "bulk_enable")],
    )
    def test_direction(self, enabled, called, other):
        api = fake_panel_api(**{called: BulkResult()})

        asyncio.run(set_clients_enabled(api, ["a@best-eu.org"], enabled))

        getattr(api.client, called).assert_awaited_once_with(["a@best-eu.org"])
        getattr(api.client, other).assert_not_called()

    def test_skipped_client_is_an_error(self):
        # Иначе джоб пометил бы человека отключённым, а его ключ продолжил бы работать.
        api = fake_panel_api(bulk_disable=_skipped("b@best-eu.org", "traffic writer queue full"))

        with pytest.raises(XuiApiError, match=r"b@best-eu\.org \(traffic writer queue full\)"):
            asyncio.run(set_clients_enabled(api, ["a@best-eu.org", "b@best-eu.org"], False))

    def test_empty_list_sends_nothing(self):
        api = fake_panel_api()

        asyncio.run(set_clients_enabled(api, [], False))

        api.client.bulk_disable.assert_not_called()


def _manual_client(**fields) -> ClientDetails:
    """Клиент, заведённый в панели руками."""
    defaults = {"email": "ivan@best-eu.org", "enable": True, "uuid": "u1", "sub_id": "s1"}
    return ClientDetails(client=Client(**(defaults | fields)), inbound_ids=[1, 2])


class TestAdoptClient:
    def _adopt(self, details: ClientDetails) -> Client:
        api = fake_panel_api()
        asyncio.run(vpn_service._adopt_client(api, details, PERSON, MEMBER))
        api.client.update.assert_awaited_once()
        return api.client.update.await_args.args[1]

    def test_writes_ownership_and_enables(self):
        client = self._adopt(_manual_client(enable=False, flow="", comment="старое", tg_id=0, group=""))

        assert client.enable is True
        assert client.flow == vpn_service.DEFAULT_FLOW
        assert client.comment == "Иванов Иван"
        assert client.tg_id == 100
        assert client.group == settings.xui.GROUP

    def test_keeps_what_was_set_by_hand(self):
        # Панель заменяет клиента телом запроса, поэтому бот правит прочитанного, а не собирает нового.
        client = self._adopt(_manual_client(limit_ip=5, total_gb=1024, expiry_time=1893456000000, reset=7))

        assert (client.limit_ip, client.total_gb, client.expiry_time, client.reset) == (5, 1024, 1893456000000, 7)


class TestAcquireClient:
    @pytest.fixture(autouse=True)
    def _inbounds(self, monkeypatch):
        monkeypatch.setattr(settings.xui, "INBOUND_IDS", [1, 2])

    def test_new_client_goes_to_all_inbounds_in_one_request(self):
        api = fake_panel_api(get_details=None, bulk_add=BulkResult(count=1))

        email, sub_id, uuid = asyncio.run(vpn_service._acquire_client(None, api, PERSON, MEMBER))

        [entry] = api.client.bulk_add.await_args.args[0]
        assert entry.inbound_ids == [1, 2]
        assert (email, sub_id, uuid) == (entry.client.email, entry.client.sub_id, entry.client.id)
        assert entry.client.flow == vpn_service.DEFAULT_FLOW
        assert entry.client.limit_ip == settings.xui.CLIENT_IP_LIMIT
        assert entry.client.reset == settings.xui.TRAFFIC_RESET_DAYS

    def test_skipped_client_is_an_error(self):
        # Дубль email и неверный инбаунд приходят в skipped: строку в БД писать нельзя.
        api = fake_panel_api(get_details=None, bulk_add=_skipped("ivan@best-eu.org", "email already in use"))

        with pytest.raises(XuiApiError, match="email already in use"):
            asyncio.run(vpn_service._acquire_client(None, api, PERSON, MEMBER))

    def test_existing_client_keeps_its_identifiers(self, monkeypatch):
        # Иначе ссылка-подписка человека перестала бы работать.
        async def no_subscription(session, email):
            return None

        monkeypatch.setattr(vpn_service, "get_subscription_by_email", no_subscription)
        api = fake_panel_api(get_details=_manual_client(tg_id=100, comment="Иванов Иван"))

        result = asyncio.run(vpn_service._acquire_client(None, api, PERSON, MEMBER))

        assert result == ("ivan@best-eu.org", "s1", "u1")
        api.client.bulk_add.assert_not_called()


NAME = "awg-1-ivan@best-eu.org"
AWG_DETAILS = ClientDetails(
    client=Client(email=NAME, enable=True, private_key="key", allowed_ips=["10.8.1.2/32"]),
    inbound_ids=[3],
    tunnel_allowed_ips={3: "10.70.0.9/32"},
)


class TestAwgClient:
    def test_find_peer_combines_client_and_traffic(self):
        api = fake_panel_api(get_details=AWG_DETAILS, get_traffic=ClientTraffic(up=10, down=20))

        peer = asyncio.run(AwgClient(api, 3).find_peer(NAME))

        assert peer.address == "10.70.0.9/32"
        assert peer.private_key == "key"
        assert (peer.up, peer.down) == (10, 20)

    def test_missing_peer_is_none(self):
        client = AwgClient(fake_panel_api(get_details=None), 3)

        assert asyncio.run(client.find_peer(NAME)) is None
        assert asyncio.run(client.has_client(NAME)) is False

    def test_client_outside_the_inbound_is_an_error(self):
        # Создать такого заново не даст уникальность email: человек застрял бы без объяснения.
        client = AwgClient(fake_panel_api(get_details=AWG_DETAILS), 4)

        with pytest.raises(AwgError, match="не в AmneziaWG-инбаунде"):
            asyncio.run(client.find_peer(NAME))

    @pytest.mark.parametrize("error", [httpx.ReadTimeout(""), XuiApiError("failed"), ValueError("cannot resolve")])
    def test_panel_failure_is_awg_error(self, error):
        # Диалоги AmneziaWG ловят только AwgError.
        with pytest.raises(AwgError):
            asyncio.run(AwgClient(fake_panel_api(delete=error), 3).remove_peer(NAME))

    def test_create_peer_leaves_keys_to_the_panel(self):
        api = fake_panel_api()

        asyncio.run(AwgClient(api, 3, "AWG").create_peer(NAME, "Иванов Иван", 100))

        inbound_id, [client] = api.client.add.await_args.args
        assert inbound_id == 3
        assert client.group == "AWG"
        assert client.keep_alive == 25
        assert (client.id, client.private_key, client.public_key, client.allowed_ips) == (None, "", "", [])

    def test_skipped_device_is_awg_error(self):
        api = fake_panel_api(bulk_disable=_skipped(NAME, "queue full"))

        with pytest.raises(AwgError, match="queue full"):
            asyncio.run(AwgClient(api, 3).set_disabled([NAME], True))
