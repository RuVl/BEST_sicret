from datetime import UTC, datetime, timedelta

import pytest

from includes.awg import (
    AwgError,
    AwgInbound,
    AwgPeer,
    build_client_config,
    build_peer_comment,
    device_client_name,
    effective_mtu,
    free_device_number,
    is_valid_client_name,
    normalize_device_label,
    render_config_qr,
)
from includes.vpn import ClientTraffic

# Инбаунд в том виде, в каком его отдаёт GET /panel/api/inbounds/get/:id (ключи ненастоящие).
INBOUND = {
    "id": 3,
    "protocol": "amneziawg",
    "remark": "BEST AWG test",
    "listen": "45.136.228.156",
    "port": 51900,
    "settings": """{"clients": [], "server": {
        "privateKey": "0000000000000000000000000000000000000000000=",
        "publicKey": "1111111111111111111111111111111111111111111=",
        "primaryDns": "94.140.14.14", "secondaryDns": "94.140.15.15",
        "jc": 3, "jmin": 55, "jmax": 294, "s1": 112, "s2": 98, "s3": 38, "s4": 27,
        "h1": "127423176", "h2": 776342377, "h3": "1094690827", "h4": "1729788298",
        "i1": "<r 186>",
        "headerProtectionKey": "2222222222222222222222222222222222222222222=",
        "contentPaddingAddition": "24-36", "rekeyAfterTime": "110-140", "rekeyTimeout": "4-7",
        "rejectAfterTime": "200-268", "keepaliveTimeout": "10-18", "maxHandshakeAttempts": "20-33",
        "randomTrailers": true, "disableCookies": true,
        "subnetIp": "10.70.0.0", "subnetCidr": 20}}""",
}

# Ответ GET /panel/api/clients/get/:email для устройства.
CLIENT_OBJ = {
    "client": {
        "id": 12,
        "email": "lbg42-1",
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


def _peer(**client) -> AwgPeer:
    return AwgPeer.from_panel({**CLIENT_OBJ, "client": CLIENT_OBJ["client"] | client}, 3, None)


class TestClientName:
    def test_device_name_fits_installer_rules(self):
        assert device_client_name(42, 1) == "lbg42-1"
        # С запасом: семизначный person_id и двузначный номер устройства укладываются в 15 символов.
        assert is_valid_client_name(device_client_name(10**7 - 1, 99))

    @pytest.mark.parametrize("name", ["ivan_pc", "lbg-7", "A1", "x" * 15])
    def test_valid(self, name):
        assert is_valid_client_name(name)

    @pytest.mark.parametrize("name", ["", "x" * 16, "иван", "ivan pc", "a/b", "a.b"])
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
        peer = AwgPeer.from_panel({**CLIENT_OBJ, "tunnelAllowedIPs": {}}, 3, None)
        assert peer.address == "10.0.0.9/32"

    def test_keepalive_number_and_range(self):
        assert _peer(keepAlive=25).keep_alive == "25"
        assert _peer(keepAlive="20-30").keep_alive == "20-30"
        assert _peer(keepAlive=0).keep_alive == ""

    def test_traffic_and_last_online(self):
        traffic = ClientTraffic.model_validate({"up": 10, "down": 20, "lastOnline": 1_793_407_202_000})
        peer = AwgPeer.from_panel(CLIENT_OBJ, 3, traffic)
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


class TestInbound:
    def test_parses_settings_string(self):
        inbound = AwgInbound.from_panel(INBOUND)
        assert (inbound.listen, inbound.port) == ("45.136.228.156", 51900)
        assert inbound.server.public_key.startswith("111")
        # H может прийти и числом - в конфиг он уходит строкой как есть.
        assert inbound.server.h2 == "776342377"
        assert inbound.server.random_trailers and inbound.server.disable_cookies


class TestEffectiveMtu:
    def test_explicit_mtu_wins(self):
        assert effective_mtu(1380, 27) == 1380

    def test_shrinks_by_s4(self):
        assert effective_mtu(0, 27) == 1393

    def test_never_below_ipv6_minimum(self):
        assert effective_mtu(0, 500) == 1280


class TestClientConfig:
    def _config(self) -> str:
        return build_client_config(_peer(), AwgInbound.from_panel(INBOUND), "45.136.228.156", "BEST-AWG - Телефон")

    def test_interface_and_peer(self):
        lines = self._config().splitlines()
        assert lines[:4] == [
            "[Interface]",
            "PrivateKey = 3333333333333333333333333333333333333333333=",
            "Address = 10.70.0.2/32",
            "DNS = 94.140.14.14, 94.140.15.15",
        ]
        assert "MTU = 1393" in lines
        assert "Endpoint = 45.136.228.156:51900" in lines
        assert "PublicKey = 1111111111111111111111111111111111111111111=" in lines
        assert "PersistentKeepalive = 25" in lines
        assert "# BEST-AWG - Телефон" in lines
        # Приватный ключ сервера в клиентский конфиг попадать не должен.
        assert "0000000000000000000000000000000000000000000=" not in self._config()

    def test_awg31_parameters_match_server(self):
        lines = self._config().splitlines()
        for line in (
            "Jc = 3",
            "S4 = 27",
            "H2 = 776342377",
            "I1 = <r 186>",
            "HeaderProtectionKey = 2222222222222222222222222222222222222222222=",
            "ContentPaddingAddition = 24-36",
            "MaxHandshakeAttempts = 20-33",
            "RandomTrailers = on",
            "DisableCookies = on",
        ):
            assert line in lines

    def test_blank_h_falls_back_to_wireguard_types(self):
        inbound = AwgInbound.from_panel(INBOUND)
        inbound.server.h1 = ""
        assert "H1 = 1" in build_client_config(_peer(), inbound, "203.0.113.1").splitlines()

    def test_line_break_in_value_is_rejected(self):
        # Иначе значение открыло бы новую секцию с PostUp, который wg-quick выполнит от root.
        inbound = AwgInbound.from_panel(INBOUND)
        inbound.server.i1 = "<r 10>\nPostUp = id"
        with pytest.raises(AwgError):
            build_client_config(_peer(), inbound, "203.0.113.1")

    def test_missing_keys_are_an_error(self):
        with pytest.raises(AwgError):
            build_client_config(_peer(privateKey=""), AwgInbound.from_panel(INBOUND), "203.0.113.1")

    def test_fits_into_qr(self):
        assert render_config_qr(self._config()).startswith(b"\x89PNG")


class TestQr:
    def test_oversized_config_raises_value_error(self):
        # Хэндлер ловит ValueError и шлёт только файл - проверяем, что segno кидает именно его.
        with pytest.raises(ValueError):
            render_config_qr("[Interface]\nI1 = <b 0x" + "ab" * 3000 + ">")
