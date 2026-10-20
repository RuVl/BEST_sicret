import pytest

from includes.awg import (
    AwgPeer,
    AwgUsageSummary,
    build_peer_comment,
    device_client_name,
    free_device_number,
    is_valid_client_name,
    normalize_device_label,
    render_config_qr,
)

# Конфиг AWG 2.0 в том виде, в каком его отдаёт установщик (ключи ненастоящие).
CONFIG = """[Interface]
PrivateKey = 0000000000000000000000000000000000000000000=
Address = 10.66.66.2/32,fd42:42:42::2/128
DNS = 1.1.1.1,1.0.0.1
Jc = 5
Jmin = 50
Jmax = 1000
S1 = 70
S2 = 86
S3 = 30
S4 = 20
H1 = 1020325451-1179015783
H2 = 1384948592-1520611946
H3 = 1726396911-1922372431
H4 = 2002412362-2147483647

[Peer]
PublicKey = 1111111111111111111111111111111111111111111=
PresharedKey = 2222222222222222222222222222222222222222222=
Endpoint = 203.0.113.10:443
AllowedIPs = 0.0.0.0/0,::/0"""


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
    def test_with_label(self):
        assert build_peer_comment("Иванов Иван", "ivan", 7, 2, "Ноутбук").endswith("«Ноутбук» - выдан ботом")

    def test_with_username(self):
        assert (
            build_peer_comment("Иванов Иван", "ivan", 7, 2) == "Иванов Иван (@ivan, tg 7), устройство 2 - выдан ботом"
        )

    def test_without_username(self):
        assert "без username" in build_peer_comment("Иванов Иван", None, 7, 1)


class TestAwgPeer:
    def test_parses_panel_summary(self):
        peer = AwgPeer.model_validate(
            {
                "id": 3,
                "name": "lbg42",
                "public_key": "ignored",
                "friendly_name": "lbg42",
                "has_config": True,
                "connection_status": "never",
                "identity_status": "linked",
                "rx_bytes": 0,
                "tx_bytes": 0,
            }
        )
        assert peer.id == 3
        assert peer.friendly_name == "lbg42"
        assert not peer.disabled

    def test_parses_handshake_time(self):
        peer = AwgPeer.model_validate({"id": 1, "latest_handshake_at": "2026-10-20T14:45:00Z"})
        assert peer.latest_handshake_at is not None and peer.latest_handshake_at.hour == 14

    def test_disabled_status(self):
        assert AwgPeer.model_validate({"id": 1, "connection_status": "disabled"}).disabled


class TestUsageSummary:
    def test_bytes_come_as_strings(self):
        summary = AwgUsageSummary.model_validate(
            {"peer_id": 1, "day": {"rx_bytes": "10", "tx_bytes": "20"}, "week": {}, "month": {"rx_bytes": "5"}}
        )
        assert (summary.day.rx_bytes, summary.day.tx_bytes, summary.month.rx_bytes) == (10, 20, 5)


class TestQr:
    def test_awg2_config_fits_into_png(self):
        assert render_config_qr(CONFIG).startswith(b"\x89PNG")

    def test_oversized_config_raises_value_error(self):
        # Хэндлер ловит ValueError и шлёт только файл - проверяем, что segno кидает именно его.
        with pytest.raises(ValueError):
            render_config_qr(CONFIG + "\nI1 = <b 0x" + "ab" * 3000 + ">")
