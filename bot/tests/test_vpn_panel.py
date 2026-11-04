"""Бот поверх настоящего py3xui: ответы сняты с панели 3x-ui v3.11.0 (ключи заменены), подменён только транспорт."""

import asyncio
from types import SimpleNamespace

import httpx
import pytest
from py3xui import XuiApiError

from env import settings
from includes.awg.client import AwgClient
from includes.awg.exceptions import AwgAuthError, AwgError
from includes.awg.schemas import AwgPeer
from includes.vpn import (
    PANEL_ERRORS,
    get_xui_api,
    is_auth_error,
    panel,
    panel_error_text,
    set_clients_enabled,
    subscription_url,
)
from includes.vpn import service as vpn_service
from tests.fakes import FakePanel, panel_failure

VLESS_OBJ = {
    "client": {
        "id": 1,
        "email": "ivan@best-eu.org",
        "subId": "a96609fead23416ab837dd252b89cab3",
        "uuid": "522fc50d-a754-4c49-80cd-3475cc6b4f71",
        "password": "",
        "auth": "",
        "flow": "xtls-rprx-vision",
        "security": "",
        "privateKey": "",
        "publicKey": "",
        "allowedIPs": "",
        "preSharedKey": "",
        "keepAlive": 0,
        "forwardedPorts": "",
        "secret": "",
        "adTag": "",
        "limitIp": 3,
        "limitHwid": 0,
        "totalGB": 0,
        "expiryTime": 0,
        "enable": True,
        "tgId": 123456789,
        "group": "SPb LBG members",
        "comment": "Иванов Иван",
        "reset": 30,
        "resetDay": 0,
        "resetWeekday": 0,
        "resetMax": 0,
        "trafficReset": "never",
        "trafficResetDay": 1,
        "createdAt": 1793744715198,
        "updatedAt": 1793744715000,
        "reverse": None,
    },
    "externalLinks": [],
    "inboundIds": [1, 2],
    "tunnelAllowedIPs": {},
    "usedTraffic": 0,
}

AWG_OBJ = {
    "client": VLESS_OBJ["client"]
    | {
        "id": 3,
        "email": "awg-1-ivan@best-eu.org",
        "uuid": "",
        "flow": "",
        "privateKey": "3333333333333333333333333333333333333333333=",
        "publicKey": "4444444444444444444444444444444444444444444=",
        "allowedIPs": "10.8.1.2/32",
        "keepAlive": 25,
        "limitIp": 0,
        "group": "AWG",
        "reset": 0,
    },
    "externalLinks": [],
    "inboundIds": [3],
    "tunnelAllowedIPs": {"3": "10.70.0.9/32"},
    "usedTraffic": 0,
}

TRAFFIC_OBJ = {
    "id": 1,
    "inboundId": 1,
    "enable": True,
    "email": "ivan@best-eu.org",
    "uuid": "522fc50d-a754-4c49-80cd-3475cc6b4f71",
    "subId": "a96609fead23416ab837dd252b89cab3",
    "up": 1048576,
    "down": 2097152,
    "expiryTime": 0,
    "total": 0,
    "reset": 30,
    "resetDay": 0,
    "resetWeekday": 0,
    "resetMax": 0,
    "resetCount": 0,
    "lastOnline": 1735680000000,
    "lastSubFetch": 0,
}

NOT_FOUND = "Obtain (record not found)"


class TestRealResponses:
    def test_vless_client(self, monkeypatch):
        fake = FakePanel(monkeypatch, {"/clients/get/": VLESS_OBJ})

        details = asyncio.run(fake.api.client.get_details("ivan@best-eu.org"))

        assert details.client.uuid == "522fc50d-a754-4c49-80cd-3475cc6b4f71"
        assert details.client.sub_id == "a96609fead23416ab837dd252b89cab3"
        assert details.client.tg_id == 123456789
        assert details.inbound_ids == [1, 2]

    def test_missing_client_is_none(self, monkeypatch):
        fake = FakePanel(monkeypatch, {"/clients/get/": panel_failure(NOT_FOUND)})

        assert asyncio.run(fake.api.client.get_details("nobody@best-eu.org")) is None

    def test_missing_traffic_is_none(self, monkeypatch):
        fake = FakePanel(monkeypatch, {"/clients/traffic/": None})

        assert asyncio.run(fake.api.client.get_traffic("nobody@best-eu.org")) is None

    def test_awg_peer_takes_address_of_this_inbound(self, monkeypatch):
        # Ключи tunnelAllowedIPs у библиотеки - int: поиск по str молча ушёл бы в общий allowedIPs.
        fake = FakePanel(monkeypatch, {"/clients/get/": AWG_OBJ})

        details = asyncio.run(fake.api.client.get_details("awg-1-ivan@best-eu.org"))
        peer = AwgPeer.from_panel(details, 3, None)

        assert peer.address == "10.70.0.9/32"
        assert peer.private_key == AWG_OBJ["client"]["privateKey"]
        assert peer.keep_alive == "25"


class TestPanelErrors:
    @pytest.mark.parametrize(
        "answer",
        [
            httpx.Response(404),
            httpx.Response(500),
            httpx.Response(200, text="<html>login</html>"),
            httpx.Response(200, json=["не", "объект"]),
            panel_failure("Something went wrong"),
            httpx.ReadTimeout(""),
            httpx.ConnectError("All connection attempts failed"),
        ],
    )
    def test_any_panel_failure_is_caught_and_has_text(self, monkeypatch, answer):
        fake = FakePanel(monkeypatch, {"/clients/traffic/": answer})

        with pytest.raises(PANEL_ERRORS) as caught:
            asyncio.run(fake.api.client.get_traffic("ivan@best-eu.org"))

        assert panel_error_text(caught.value)

    def test_panel_404_does_not_look_like_a_missing_client(self, monkeypatch):
        # 404 - неверный путь панели, а не отсутствующий клиент.
        fake = FakePanel(monkeypatch, {"/clients/get/": httpx.Response(404)})

        with pytest.raises(httpx.HTTPStatusError):
            asyncio.run(fake.api.client.get_details("ivan@best-eu.org"))

    @pytest.mark.parametrize("status", [401, 403])
    def test_auth_error(self, monkeypatch, status):
        fake = FakePanel(monkeypatch, {"/clients/get/": httpx.Response(status)})

        with pytest.raises(httpx.HTTPStatusError) as caught:
            asyncio.run(fake.api.client.get_details("ivan@best-eu.org"))

        assert is_auth_error(caught.value)

    @pytest.mark.parametrize(
        "obj",
        [
            # email обязателен: ошибка «missing» несёт весь объект клиента вместе с ключами.
            {"client": {"enable": True, "privateKey": "secret-key"}},
            {"client": VLESS_OBJ["client"] | {"privateKey": "secret-key"}, "inboundIds": "3"},
        ],
    )
    def test_malformed_response_does_not_leak_secrets(self, monkeypatch, obj):
        fake = FakePanel(monkeypatch, {"/clients/get/": obj})

        with pytest.raises(PANEL_ERRORS) as caught:
            asyncio.run(fake.api.client.get_details("ivan@best-eu.org"))

        assert "не по схеме" in panel_error_text(caught.value)
        assert "secret-key" not in panel_error_text(caught.value)

    def test_panel_message_is_used_as_is(self):
        assert panel_error_text(XuiApiError("email already in use")) == "email already in use"


class TestApiSettings:
    def test_one_attempt_and_timeout(self, monkeypatch):
        monkeypatch.setattr(settings.xui, "BASE_URL", "https://panel")
        monkeypatch.setattr(settings.xui, "API_TOKEN", "token")
        monkeypatch.setattr(panel, "_api", None)

        api = get_xui_api()

        assert api is get_xui_api()
        assert api.max_retries == 1
        assert api.timeout == 15

    def test_timeout_is_not_retried(self, monkeypatch):
        # Повтор выполненного POST вернул бы ложную ошибку: панель уже применила действие.
        fake = FakePanel(monkeypatch, {"/clients/bulkDisable": httpx.ReadTimeout("")})

        with pytest.raises(httpx.ReadTimeout):
            asyncio.run(set_clients_enabled(fake.api, ["a@best-eu.org"], False))

        assert len(fake.requests) == 1


class TestSetClientsEnabled:
    def test_skipped_clients_are_an_error(self, monkeypatch):
        # 3x-ui на неуспех отдельного клиента отвечает success=true и перечисляет его в skipped.
        skipped = [{"email": "b@best-eu.org", "reason": "traffic writer queue full"}]
        fake = FakePanel(monkeypatch, {"/clients/bulkDisable": {"changed": 1, "skipped": skipped}})

        with pytest.raises(XuiApiError, match=r"b@best-eu\.org \(traffic writer queue full\)"):
            asyncio.run(set_clients_enabled(fake.api, ["a@best-eu.org", "b@best-eu.org"], False))

    @pytest.mark.parametrize("obj", [{"changed": 2}, {"changed": 2, "skipped": None}, {"changed": 2, "skipped": []}])
    def test_nothing_skipped_is_success(self, monkeypatch, obj):
        fake = FakePanel(monkeypatch, {"/clients/bulkEnable": obj})

        asyncio.run(set_clients_enabled(fake.api, ["a@best-eu.org", "b@best-eu.org"], True))

        assert fake.requests == [("/clients/bulkEnable", {"emails": ["a@best-eu.org", "b@best-eu.org"]})]

    def test_empty_list_sends_nothing(self, monkeypatch):
        fake = FakePanel(monkeypatch, {})

        asyncio.run(set_clients_enabled(fake.api, [], False))

        assert fake.requests == []


PERSON = SimpleNamespace(id=7, telegram_id=100, full_name="Ivan Ivanov")
MEMBER = SimpleNamespace(best_email="ivan@best-eu.org", full_name_ru="Иванов Иван")


class TestAdoptClient:
    def _adopt(self, monkeypatch, **client) -> dict:
        obj = VLESS_OBJ | {"client": VLESS_OBJ["client"] | client}
        fake = FakePanel(monkeypatch, {"/clients/get/": obj, "/clients/update/": None})

        async def adopt():
            details = await fake.api.client.get_details("ivan@best-eu.org")
            await vpn_service._adopt_client(fake.api, details, PERSON, MEMBER)

        asyncio.run(adopt())
        return fake.body("/clients/update/ivan%40best-eu.org")

    def test_uuid_goes_into_id(self, monkeypatch):
        body = self._adopt(monkeypatch)

        # На запись UUID называется id, числовой id строки панели отправлять нельзя.
        assert body["id"] == "522fc50d-a754-4c49-80cd-3475cc6b4f71"

    def test_writes_ownership_and_enables(self, monkeypatch):
        body = self._adopt(monkeypatch, enable=False, flow="", comment="старое", tgId=0, group="")

        assert body["enable"] is True
        assert body["flow"] == vpn_service.DEFAULT_FLOW
        assert body["comment"] == "Иванов Иван"
        assert body["tgId"] == 100
        assert body["group"] == settings.xui.GROUP

    def test_keeps_what_was_set_by_hand(self, monkeypatch):
        # Панель заменяет клиента телом запроса: всё, чего нет в теле, обнулится.
        body = self._adopt(
            monkeypatch,
            limitIp=5,
            totalGB=1024,
            expiryTime=1893456000000,
            reset=7,
            password="trojan-secret",
            reverse={"tag": "r1"},
            fieldFromNewerPanel="value",
        )

        assert body["limitIp"] == 5
        assert body["totalGB"] == 1024
        assert body["expiryTime"] == 1893456000000
        assert body["reset"] == 7
        assert body["password"] == "trojan-secret"
        assert body["reverse"] == {"tag": "r1"}
        assert body["fieldFromNewerPanel"] == "value"

    def test_allowed_ips_are_a_list(self, monkeypatch):
        # GET отдаёт строку, а панель разбирает тело в []string: строка уронила бы update целиком.
        body = self._adopt(monkeypatch, allowedIPs="10.70.0.2/32,fd00::2/128")

        assert body["allowedIPs"] == ["10.70.0.2/32", "fd00::2/128"]

    def test_stored_reverse_that_is_not_an_object_is_not_sent(self, monkeypatch):
        assert "reverse" not in self._adopt(monkeypatch, reverse="legacy")


class TestAcquireClient:
    def _acquire(self, monkeypatch, created: object) -> tuple[tuple[str, str, str], FakePanel]:
        monkeypatch.setattr(settings.xui, "INBOUND_IDS", [1, 2])
        fake = FakePanel(
            monkeypatch,
            {"/clients/get/": panel_failure(NOT_FOUND), "/clients/bulkCreate": created},
        )
        return asyncio.run(vpn_service._acquire_client(None, fake.api, PERSON, MEMBER)), fake

    def test_new_client_goes_to_all_inbounds_in_one_request(self, monkeypatch):
        (email, sub_id, uuid), fake = self._acquire(monkeypatch, {"created": 1})

        [entry] = fake.body("/clients/bulkCreate")
        assert entry["inboundIds"] == [1, 2]
        client = entry["client"]
        assert (email, sub_id, uuid) == (client["email"], client["subId"], client["id"])
        assert client["flow"] == vpn_service.DEFAULT_FLOW
        assert client["enable"] is True
        assert client["tgId"] == 100
        assert client["comment"] == "Иванов Иван"
        assert client["limitIp"] == settings.xui.CLIENT_IP_LIMIT
        assert client["reset"] == settings.xui.TRAFFIC_RESET_DAYS

    def test_skipped_client_is_an_error(self, monkeypatch):
        # Дубль email и неверный инбаунд панель возвращает как success=true со skipped: БД писать нельзя.
        skipped = {"created": 0, "skipped": [{"email": "ivan@best-eu.org", "reason": "email already in use"}]}

        with pytest.raises(XuiApiError, match="email already in use"):
            self._acquire(monkeypatch, skipped)


class TestSubscriptionUrl:
    def test_joins_without_double_slash(self, monkeypatch):
        monkeypatch.setattr(settings.xui, "SUB_BASE_URL", "https://vpn.example.org/sub/")

        assert subscription_url("abc") == "https://vpn.example.org/sub/abc"


class TestAwgClient:
    def _client(self, monkeypatch, routes: dict[str, object]) -> tuple[AwgClient, FakePanel]:
        fake = FakePanel(monkeypatch, routes)
        return AwgClient(fake.api, 3, "AWG"), fake

    def test_find_peer(self, monkeypatch):
        client, _ = self._client(monkeypatch, {"/clients/get/": AWG_OBJ, "/clients/traffic/": TRAFFIC_OBJ})

        peer = asyncio.run(client.find_peer("awg-1-ivan@best-eu.org"))

        assert peer.address == "10.70.0.9/32"
        assert (peer.up, peer.down) == (1048576, 2097152)

    def test_missing_peer_is_none(self, monkeypatch):
        client, _ = self._client(monkeypatch, {"/clients/get/": panel_failure(NOT_FOUND)})

        assert asyncio.run(client.find_peer("awg-1-ivan@best-eu.org")) is None
        assert asyncio.run(client.has_client("awg-1-ivan@best-eu.org")) is False

    def test_client_outside_the_inbound_is_an_error(self, monkeypatch):
        client, _ = self._client(monkeypatch, {"/clients/get/": AWG_OBJ | {"inboundIds": [1]}})

        with pytest.raises(AwgError, match="не в AmneziaWG-инбаунде"):
            asyncio.run(client.find_peer("awg-1-ivan@best-eu.org"))

    def test_rejected_token_is_auth_error(self, monkeypatch):
        client, _ = self._client(monkeypatch, {"/clients/get/": httpx.Response(401)})

        with pytest.raises(AwgAuthError):
            asyncio.run(client.find_peer("awg-1-ivan@best-eu.org"))

    def test_timeout_is_awg_error(self, monkeypatch):
        client, _ = self._client(monkeypatch, {"/clients/get/": httpx.ReadTimeout("")})

        with pytest.raises(AwgError, match="ReadTimeout"):
            asyncio.run(client.find_peer("awg-1-ivan@best-eu.org"))

    def test_create_peer_leaves_keys_to_the_panel(self, monkeypatch):
        client, fake = self._client(monkeypatch, {"/clients/add": None})

        asyncio.run(client.create_peer("awg-1-ivan@best-eu.org", "Иванов Иван", 100))

        body = fake.body("/clients/add")
        assert body["inboundIds"] == [3]
        created = body["client"]
        assert created["email"] == "awg-1-ivan@best-eu.org"
        assert created["keepAlive"] == 25
        assert created["group"] == "AWG"
        assert not {"id", "privateKey", "publicKey", "allowedIPs"} & created.keys()

    def test_duplicate_email_is_awg_error(self, monkeypatch):
        client, _ = self._client(monkeypatch, {"/clients/add": panel_failure("email already in use")})

        with pytest.raises(AwgError, match="email already in use"):
            asyncio.run(client.create_peer("awg-1-ivan@best-eu.org", "Иванов Иван", 100))

    def test_remove_peer_by_email(self, monkeypatch):
        client, fake = self._client(monkeypatch, {"/clients/del/": None})

        asyncio.run(client.remove_peer("awg-1-ivan@best-eu.org"))

        assert [path for path, _ in fake.requests] == ["/clients/del/awg-1-ivan%40best-eu.org"]

    def test_remove_peer_with_name_without_at_sign(self, monkeypatch):
        # Запасные имена awg-<n>-lbg-<id> не содержат @.
        listed = [{"id": 5, "uuid": "", "email": "awg-1-lbg-7"}]
        client, fake = self._client(monkeypatch, {"/clients/list": listed, "/clients/del/": None})

        asyncio.run(client.remove_peer("awg-1-lbg-7"))

        assert fake.requests[-1][0] == "/clients/del/awg-1-lbg-7"

    def test_skipped_device_is_awg_error(self, monkeypatch):
        skipped = {"changed": 0, "skipped": [{"email": "awg-1-lbg-7", "reason": "queue full"}]}
        client, _ = self._client(monkeypatch, {"/clients/bulkDisable": skipped})

        with pytest.raises(AwgError, match="queue full"):
            asyncio.run(client.set_disabled(["awg-1-lbg-7"], True))
