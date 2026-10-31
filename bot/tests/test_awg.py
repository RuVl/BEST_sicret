import base64
from datetime import UTC, datetime, timedelta

import pytest

from includes.awg import (
    AwgError,
    AwgPeer,
    build_peer_comment,
    device_client_name,
    extract_device_config,
    free_device_number,
    is_valid_client_name,
    normalize_device_label,
    render_config_qr,
)
from includes.vpn import ClientDetails, ClientTraffic

# Ответ GET /panel/api/clients/get/:email для устройства (ключи ненастоящие).
CLIENT_OBJ = {
    "client": {
        "id": 12,
        "email": "awg-lbg42-1",
        "subId": "abc",
        "enable": True,
        "privateKey": "3333333333333333333333333333333333333333333=",
        "publicKey": "4444444444444444444444444444444444444444444=",
        "allowedIPs": "10.0.0.9/32",
        "keepAlive": 25,
    },
    "inboundIds": [3],
    "tunnelAllowedIPs": {"3": "10.70.0.2/32"},
}


def _details(**overrides) -> ClientDetails:
    return ClientDetails.model_validate(CLIENT_OBJ | overrides)


def _peer(**client) -> AwgPeer:
    return AwgPeer.from_panel(_details(client=CLIENT_OBJ["client"] | client), 3, None)


# Конфиг устройства, как его собирает 3x-ui (сокращён: параметры обфускации бот не разбирает).
CONF = """[Interface]
PrivateKey = 3333333333333333333333333333333333333333333=
Address = 10.70.0.2/32
DNS = 94.140.14.14, 94.140.15.15
MTU = 1393
Jc = 3
HeaderProtectionKey = 2222222222222222222222222222222222222222222=
RandomTrailers = on

# BEST AWG test
[Peer]
PublicKey = 1111111111111111111111111111111111111111111=
AllowedIPs = 0.0.0.0/0, ::/0
Endpoint = 45.136.228.156:443
PersistentKeepalive = 25"""


def _vpn_link(conf: str) -> str:
    # Как genAmneziaWGLink панели: base64url без паддинга.
    return "vpn://" + base64.urlsafe_b64encode(conf.encode()).decode().rstrip("=")


class TestClientName:
    def test_device_name_is_marked_as_awg(self):
        assert device_client_name(42, 1) == "awg-lbg42-1"
        # С запасом: семизначный person_id и двузначный номер устройства укладываются в колонку.
        assert is_valid_client_name(device_client_name(10**7 - 1, 99))

    @pytest.mark.parametrize("name", ["ivan_pc", "lbg-7", "A1", "x" * 32])
    def test_valid(self, name):
        assert is_valid_client_name(name)

    @pytest.mark.parametrize("name", ["", "x" * 33, "иван", "ivan pc", "a/b", "a.b"])
    def test_invalid(self, name):
        assert not is_valid_client_name(name)


class TestFreeDeviceNumber:
    def test_first_device(self):
        assert free_device_number([]) == 1

    def test_next_after_taken(self):
        assert free_device_number([1, 2]) == 3

    def test_reuses_number_of_deleted_device(self):
        assert free_device_number([1, 3]) == 2


class TestDeviceLabel:
    def test_collapses_whitespace(self):
        assert normalize_device_label("  Мой   телефон\n") == "Мой телефон"

    def test_keeps_emoji(self):
        assert normalize_device_label("📱 iPhone") == "📱 iPhone"

    @pytest.mark.parametrize("value", ["", "   ", "x" * 33])
    def test_rejects(self, value):
        with pytest.raises(ValueError):
            normalize_device_label(value)


class TestPeerComment:
    def test_with_username(self):
        assert (
            build_peer_comment("Иванов Иван", "ivan", 7, 2) == "Иванов Иван (@ivan, tg 7), устройство 2 - выдан ботом"
        )

    def test_without_username(self):
        assert "без username" in build_peer_comment("Иванов Иван", None, 7, 1)


class TestAwgPeer:
    def test_address_comes_from_this_inbound(self):
        # Общая колонка allowedIPs может держать адрес WireGuard-инбаунда - в конфиг он не годится.
        assert _peer().address == "10.70.0.2/32"

    def test_falls_back_to_shared_address(self):
        peer = AwgPeer.from_panel(_details(tunnelAllowedIPs={}), 3, None)
        assert peer.address == "10.0.0.9/32"

    def test_keepalive_number_and_range(self):
        assert _peer(keepAlive=25).keep_alive == "25"
        assert _peer(keepAlive="20-30").keep_alive == "20-30"
        assert _peer(keepAlive=0).keep_alive == ""

    def test_traffic_and_last_online(self):
        traffic = ClientTraffic.model_validate({"up": 10, "down": 20, "lastOnline": 1_793_407_202_000})
        peer = AwgPeer.from_panel(_details(), 3, traffic)
        assert (peer.up, peer.down) == (10, 20)
        assert peer.last_online_at == datetime.fromtimestamp(1_793_407_202, UTC)

    def test_statuses(self):
        now = datetime(2026, 10, 31, 12, 0, tzinfo=UTC)
        assert _peer(enable=False).connection_status(now) == "disabled"
        assert _peer().connection_status(now) == "never"
        recent = _peer().model_copy(update={"last_online_at": now - timedelta(minutes=1)})
        assert recent.connection_status(now) == "online"
        stale = _peer().model_copy(update={"last_online_at": now - timedelta(hours=1)})
        assert stale.connection_status(now) == "inactive"


class TestShareLink:
    def test_picks_device_config_among_other_links(self):
        other_device = CONF.replace("PrivateKey = 333", "PrivateKey = 555")
        links = ["vless://uuid@host:443?type=xhttp#BEST", _vpn_link(other_device), _vpn_link(CONF)]
        assert extract_device_config(links, _peer()) == CONF + "\n"

    def test_other_inbound_of_same_client_is_skipped(self):
        # Тот же клиент в другом AmneziaWG-инбаунде - другой адрес туннеля.
        elsewhere = CONF.replace("Address = 10.70.0.2/32", "Address = 10.80.0.2/32")
        with pytest.raises(AwgError):
            extract_device_config([_vpn_link(elsewhere)], _peer())

    def test_address_with_ipv6(self):
        dual = CONF.replace("Address = 10.70.0.2/32", "Address = 10.70.0.2/32, fd00::2/128")
        assert "fd00::2/128" in extract_device_config([_vpn_link(dual)], _peer())

    def test_no_awg_link_is_an_error(self):
        with pytest.raises(AwgError):
            extract_device_config(["vless://uuid@host:443", "vpn://не-base64!"], _peer())

    @pytest.mark.parametrize("endpoint", ["127.0.0.1:443", "10.0.0.5:443", "localhost:443", ":443"])
    def test_internal_endpoint_is_rejected(self, endpoint):
        # Без Listen IP панель подставила бы адрес, по которому к ней ходит бот, - снаружи он не работает.
        conf = CONF.replace("Endpoint = 45.136.228.156:443", f"Endpoint = {endpoint}")
        with pytest.raises(AwgError):
            extract_device_config([_vpn_link(conf)], _peer())

    def test_missing_private_key_is_an_error(self):
        with pytest.raises(AwgError):
            extract_device_config([_vpn_link(CONF)], _peer(privateKey=""))

    def test_fits_into_qr(self):
        assert render_config_qr(CONF).startswith(b"\x89PNG")


class TestQr:
    def test_oversized_config_raises_value_error(self):
        # Хэндлер ловит ValueError и шлёт только файл - проверяем, что segno кидает именно его.
        with pytest.raises(ValueError):
            render_config_qr("[Interface]\nI1 = <b 0x" + "ab" * 3000 + ">")
