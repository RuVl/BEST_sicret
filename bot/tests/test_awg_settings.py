"""Включён ли AmneziaWG и куда смотрит Endpoint выданного конфига."""

import pytest

from env import AwgConfig, GlobalSettings, TelegramConfig, XuiConfig
from includes.awg import AwgError
from includes.awg.share_link import _check_endpoint


def _settings(monkeypatch, **env: str) -> GlobalSettings:
    for name in ("AWG_INBOUND_ID", "XUI_BASE_URL", "XUI_API_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    return GlobalSettings(
        awg=AwgConfig(_env_file=None), xui=XuiConfig(_env_file=None), telegram=TelegramConfig(_env_file=None)
    )


class TestEnabled:
    def test_inbound_and_panel(self, monkeypatch):
        assert _settings(monkeypatch, AWG_INBOUND_ID="3", XUI_BASE_URL="https://p", XUI_API_TOKEN="t").AWG_ENABLED

    @pytest.mark.parametrize(
        "env",
        [
            {"AWG_INBOUND_ID": "0", "XUI_BASE_URL": "https://p", "XUI_API_TOKEN": "t"},
            {"AWG_INBOUND_ID": "3", "XUI_API_TOKEN": "t"},
            {"AWG_INBOUND_ID": "3", "XUI_BASE_URL": "https://p"},
        ],
    )
    def test_disabled_without_inbound_or_panel(self, monkeypatch, env):
        assert not _settings(monkeypatch, **env).AWG_ENABLED


class TestEndpoint:
    @pytest.mark.parametrize(
        "endpoint",
        [
            "host.docker.internal:443",
            "localhost:443",
            "xui:443",
            "3x-ui:443",
            "panel.local:443",
            "127.0.0.1:443",
            "10.0.0.5:443",
            ":443",
        ],
    )
    def test_internal_rejected(self, endpoint):
        with pytest.raises(AwgError):
            _check_endpoint(endpoint, "awg-1-x@best")

    @pytest.mark.parametrize("endpoint", ["vpn.example.org:443", "45.136.228.156:443", "[2a01:4f8::1]:443"])
    def test_public_accepted(self, endpoint):
        _check_endpoint(endpoint, "awg-1-x@best")
