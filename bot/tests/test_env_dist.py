"""Шаблоны конфигов: на них живёт первый запуск, и заглушка в них незаметно включает внешние сервисы."""

from pathlib import Path

import pytest
from dotenv import dotenv_values

from env import ProjectConfig, XuiConfig

_BOT_DIR = Path(__file__).resolve().parents[1]
_ENV_DIST = _BOT_DIR / ".env.dist"
_DEV_ENV_DIST = _BOT_DIR / "dev.env.dist"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("XUI_BASE_URL", "XUI_API_TOKEN", "XUI_SUB_BASE_URL", "XUI_INBOUND_IDS", "TEMPLATES_DIR"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.parametrize("files", [(_ENV_DIST,), (_ENV_DIST, _DEV_ENV_DIST)], ids=["docker", "local"])
def test_vpn_is_off_by_default(files: tuple[Path, ...]) -> None:
    config = XuiConfig(_env_file=files)

    assert not config.ENABLED
    assert not config.HAS_PANEL


def test_dev_env_does_not_shadow_panel_settings() -> None:
    """dev.env попадает в окружение процесса: даже пустая переменная перекрыла бы панель из .env."""
    assert [name for name in dotenv_values(_DEV_ENV_DIST) if name.startswith("XUI_")] == []


def test_demo_template_is_local_only() -> None:
    docker = ProjectConfig(_env_file=_ENV_DIST)
    local = ProjectConfig(_env_file=(_ENV_DIST, _DEV_ENV_DIST))

    assert docker.TEMPLATES_DIR.name == "templates"
    assert local.TEMPLATES_DIR.name == "demo_templates"
