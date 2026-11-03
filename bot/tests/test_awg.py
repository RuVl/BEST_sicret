import asyncio
import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from includes.awg import (
    AwgError,
    AwgPeer,
    device_client_name,
    extract_device_config,
    fallback_device_client_name,
    free_device_number,
    is_valid_client_name,
    normalize_device_label,
    render_config_qr,
)
from includes.vpn import ClientDetails, ClientTraffic
from jobs import revoke_vpn, suspend_awg
from tests.fakes import FakeBot, FakeL10n, FakeSessionMaker

# Ответ GET /panel/api/clients/get/:email для устройства (ключи ненастоящие).
CLIENT_OBJ = {
    "client": {
        "id": 12,
        "email": "awg-1-ivan.petrov@best-eu.org",
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
    def test_device_name_is_number_and_email(self):
        assert device_client_name(42, "ivan.petrov@best-eu.org", 1) == "awg-1-ivan.petrov@best-eu.org"

    def test_email_is_trimmed(self):
        assert device_client_name(42, "  ivan@best-eu.org ", 2) == "awg-2-ivan@best-eu.org"

    @pytest.mark.parametrize("email", [None, "", "  ", "ivan petrov@best-eu.org", "a/b@best-eu.org"])
    def test_falls_back_to_person_id(self, email):
        assert device_client_name(42, email, 3) == "awg-3-lbg-42"

    def test_fallback_name_has_no_email(self):
        # Его же бот берёт, когда имя с почтой уже заняло чужое устройство (почты в таблице не уникальны).
        assert fallback_device_client_name(42, 3) == "awg-3-lbg-42"

    def test_too_long_email_falls_back(self):
        email = "x" * 200 + "@best-eu.org"
        assert device_client_name(42, email, 1) == "awg-1-lbg-42"

    def test_long_real_email_fits(self):
        name = device_client_name(10**7 - 1, "aleksandra.rasponamareva@best-eu.org", 99)
        assert name == "awg-99-aleksandra.rasponamareva@best-eu.org"
        assert is_valid_client_name(name)

    @pytest.mark.parametrize("name", ["ivan_pc", "lbg-7", "A1", "awg-1-a.b@best-eu.org", "x" * 128])
    def test_valid(self, name):
        assert is_valid_client_name(name)

    @pytest.mark.parametrize("name", ["", "x" * 129, "ivan pc", "a/b", "a\\b", "a\tb"])
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


def _access(person_id: int) -> SimpleNamespace:
    person = SimpleNamespace(telegram_id=100 + person_id, full_name=f"Person {person_id}")
    return SimpleNamespace(person_id=person_id, person=person, status="granted", disabled_at=None)


class TestSuspendJob:
    """Ночное отключение: сбой на одном человеке не откатывает и не повторяет остальных."""

    # Что панель отвечает на выключение ключей человека: число найденных ключей или исключение.
    PANEL = {
        1: 2,
        2: AwgError("skipped: traffic writer queue full"),
        3: RuntimeError("неожиданный ответ"),
        4: 1,  # ключи выключены, а коммит упал
        5: 0,  # устройств нет - чиним запись молча
        6: 1,
    }

    def _run(self, monkeypatch, sessions: FakeSessionMaker) -> FakeBot:
        async def list_accesses_to_suspend(session):
            # Загруженные строки привязаны к сессии: её коммит сохранит и все их правки.
            accesses = [_access(person_id) for person_id in self.PANEL]
            for access in accesses:
                session.add(access)
            return accesses

        async def get_hr_id(session):
            return 1

        async def disable_peers(client, access):
            result = self.PANEL[access.person_id]
            if isinstance(result, Exception):
                raise result
            return result

        for module in (suspend_awg, revoke_vpn):
            monkeypatch.setattr(module, "async_session", sessions)
        monkeypatch.setattr(suspend_awg, "list_accesses_to_suspend", list_accesses_to_suspend)
        monkeypatch.setattr(suspend_awg, "get_hr_id", get_hr_id)
        monkeypatch.setattr(suspend_awg, "disable_peers", disable_peers)
        monkeypatch.setattr(suspend_awg, "get_awg_client", lambda: None)

        bot = FakeBot()
        asyncio.run(suspend_awg.suspend_inactive_awg_access(bot, FakeL10n()))
        return bot

    def test_each_person_is_committed_before_notice(self, monkeypatch):
        sessions = FakeSessionMaker(fail_commit=lambda row: row.person_id == 4)
        bot = self._run(monkeypatch, sessions)

        assert [row.person_id for row in sessions.committed] == [1, 5, 6]
        assert all(row.status == "suspended" for row in sessions.committed)
        notified = [chat_id for chat_id, _ in bot.sent if chat_id != 1]
        assert notified == [101, 106]

    def test_failures_go_to_report(self, monkeypatch):
        bot = self._run(monkeypatch, FakeSessionMaker(fail_commit=lambda row: row.person_id == 4))

        report = "\n".join(text for chat_id, text in bot.sent if chat_id == 1)
        assert "'revoked': 2" in report
        assert "'failed': 3" in report
        assert "Person 2" in report
        assert "Person 3" in report
        assert "Person 4" in report
