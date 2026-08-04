import pytest

from includes.vpn.client import unwrap_envelope
from includes.vpn.exceptions import XuiError
from includes.vpn.schemas import ClientRecord, ClientTraffic, XuiClientPayload

# Ответ панели на GET /panel/api/clients/get/:email (поле obj.client)
CLIENT_RECORD_FIXTURE = {
    "id": 14,
    "email": "ivan@best-eu.org",
    "uuid": "e18c9a96-71bf-48d4-933f-8b9a46d4290c",
    "subId": "i7tvdpeffi0hvvf1",
    "enable": True,
    "tgId": 123456789,
    "comment": "Иванов Иван",
    "group": "SPb LBG members",
    "limitIp": 3,
    "totalGB": 0,
    "expiryTime": 0,
    "reset": 30,
}

# Ответ панели на GET /panel/api/clients/traffic/:email
TRAFFIC_FIXTURE = {
    "id": 1,
    "inboundId": 1,
    "enable": True,
    "email": "ivan@best-eu.org",
    "up": 1048576,
    "down": 2097152,
    "expiryTime": 0,
    "total": 0,
    "reset": 30,
    "lastOnline": 1735680000000,
}


class TestClientRecord:
    def test_parses_panel_payload(self):
        record = ClientRecord.model_validate(CLIENT_RECORD_FIXTURE)

        assert record.email == "ivan@best-eu.org"
        assert record.sub_id == "i7tvdpeffi0hvvf1"
        assert record.tg_id == 123456789
        assert record.limit_ip == 3

    def test_to_payload_moves_uuid_into_id(self):
        # В теле на запись UUID называется id, а числовой id строки панели не нужен вовсе.
        payload = ClientRecord.model_validate(CLIENT_RECORD_FIXTURE).to_payload()

        assert payload.id == "e18c9a96-71bf-48d4-933f-8b9a46d4290c"

    def test_to_payload_keeps_manual_panel_settings(self):
        payload = ClientRecord.model_validate(CLIENT_RECORD_FIXTURE).to_payload()
        dumped = payload.model_dump(by_alias=True)

        assert dumped["limitIp"] == 3
        assert dumped["reset"] == 30
        assert dumped["group"] == "SPb LBG members"
        assert dumped["comment"] == "Иванов Иван"

    def test_extra_panel_fields_are_ignored(self):
        record = ClientRecord.model_validate(CLIENT_RECORD_FIXTURE | {"flow": "xtls-rprx-vision"})

        assert record.email == "ivan@best-eu.org"


class TestXuiClientPayload:
    def test_dumps_camel_case_for_panel(self):
        payload = XuiClientPayload(
            id="uuid-1",
            email="lbg-7",
            subId="sub-1",
            tgId=1,
            limitIp=3,
            totalGB=0,
            expiryTime=0,
            reset=30,
        )
        dumped = payload.model_dump(by_alias=True)

        assert dumped["subId"] == "sub-1"
        assert dumped["tgId"] == 1
        assert dumped["limitIp"] == 3
        assert dumped["totalGB"] == 0
        assert dumped["expiryTime"] == 0


class TestClientTraffic:
    def test_parses_and_sums_traffic(self):
        traffic = ClientTraffic.model_validate(TRAFFIC_FIXTURE)

        assert traffic.enable is True
        assert traffic.used_bytes == 1048576 + 2097152

    def test_defaults_are_safe_for_empty_response(self):
        traffic = ClientTraffic.model_validate({})

        assert traffic.enable is False
        assert traffic.used_bytes == 0


class TestUnwrapEnvelope:
    def test_returns_obj_on_success(self):
        assert unwrap_envelope({"success": True, "msg": "", "obj": {"a": 1}}) == {"a": 1}

    def test_raises_with_panel_message(self):
        with pytest.raises(XuiError, match="email already in use"):
            unwrap_envelope({"success": False, "msg": "email already in use", "obj": None})

    def test_raises_on_missing_success_flag(self):
        with pytest.raises(XuiError):
            unwrap_envelope({"obj": None})

    def test_raises_on_non_dict(self):
        with pytest.raises(XuiError):
            unwrap_envelope("<html>login</html>")
