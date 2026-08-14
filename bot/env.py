"""Конфигурация бота через pydantic-settings (nested-паттерн, эталон - members_sync/env.py).

Настройки сгруппированы в подмодели-секции (``TelegramConfig``/``PostgresConfig``/...), собранные
на едином ``GlobalSettings``. Каждая секция - самостоятельный ``BaseSettings``: pydantic не наполняет
вложенные ``BaseModel`` из плоских env по alias (нужен ``env_nested_delimiter`` или JSON), поэтому
секции читают ``.env`` сами.

Доступ: ``settings.telegram.API_TOKEN``.

``.env`` берётся рядом с этим файлом; реальные переменные окружения (docker ``env_file``) имеют
приоритет над файлом.
"""

from pathlib import Path
from typing import Annotated, Final

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent / ".env"


class _Section(BaseSettings):
    """Базовая секция: единый источник ``.env`` и игнор лишних переменных."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


class TelegramConfig(_Section):
    API_TOKEN: str = Field(alias="TG_API_TOKEN")
    PRESIDENT_ID: int = 0
    TREASURER_ID: int = 0


# noinspection DuplicatedCode
class PostgresConfig(_Section):
    HOST: str = Field("localhost", alias="POSTGRES_HOST")
    PORT: str = Field("5432", alias="POSTGRES_PORT")
    USER: str = Field("postgres", alias="POSTGRES_USER")
    PASSWORD: str = Field("", alias="POSTGRES_PASSWORD")
    DATABASE: str = Field("database", alias="POSTGRES_DB")

    @property
    def URL(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DATABASE}"


class RedisConfig(_Section):
    USE_REDIS: bool = Field(True, alias="USE_REDIS")
    HOST: str = Field("localhost", alias="REDIS_HOST")
    PORT: str = Field("6379", alias="REDIS_PORT")
    DATABASE: str = Field("0", alias="REDIS_DB")

    @property
    def URL(self) -> str:
        return f"redis://{self.HOST}:{self.PORT}/{self.DATABASE}"


class ProjectConfig(_Section):
    DEBUG: bool = Field(alias="DEBUG")
    RESOURCE_DIR: Path = Field(Path("resources/"), alias="RESOURCE_DIR")
    TEMPLATES_DIR: Path = Field(Path("resources/templates/"), alias="TEMPLATES_DIR")
    REFUND_BILLS_DIR: Path = Field(Path("resources/refund_bills/"), alias="REFUND_BILLS_DIR")
    LOCALE_DIR: Path = Field(Path("l10n/"), alias="LOCALE_DIR")
    # NoDecode: значение в .env - строка через запятую (``ru,en``), а не JSON-список
    AVAILABLE_LOCALES: Annotated[list[str], NoDecode] = Field(["ru"], alias="AVAILABLE_LOCALES")

    @field_validator("AVAILABLE_LOCALES", mode="before")
    @classmethod
    def split_locales(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    # Динамическая сборка путей, если они не заданы в .env явно, а зависят от RESOURCE_DIR
    @model_validator(mode="before")
    @classmethod
    def assemble_paths(cls, data: dict) -> dict:
        # Извлекаем RESOURCE_DIR, учитывая дефолтное значение
        resource_dir_raw = data.get("RESOURCE_DIR", "resources/")
        resource_dir = Path(resource_dir_raw) if isinstance(resource_dir_raw, str) else resource_dir_raw

        if "TEMPLATES_DIR" not in data:
            data["TEMPLATES_DIR"] = resource_dir / "templates/"
        if "REFUND_BILLS_DIR" not in data:
            data["REFUND_BILLS_DIR"] = resource_dir / "refund_bills/"
        return data


class XuiConfig(_Section):
    """Панель 3x-ui (v3): доступ по API-токену, выдача VPN-подписок."""

    BASE_URL: str = Field("", alias="XUI_BASE_URL")
    API_TOKEN: str = Field("", alias="XUI_API_TOKEN")
    SUB_BASE_URL: str = Field("", alias="XUI_SUB_BASE_URL")
    # NoDecode: значение в .env - строка через запятую (``1,2``), а не JSON-список
    INBOUND_IDS: Annotated[list[int], NoDecode] = Field([], alias="XUI_INBOUND_IDS")
    GROUP: str = Field("SPb LBG members", alias="XUI_GROUP")
    CLIENT_IP_LIMIT: int = Field(3, alias="XUI_CLIENT_IP_LIMIT")
    TRAFFIC_RESET_DAYS: int = Field(30, alias="XUI_TRAFFIC_RESET_DAYS")

    # Отзыв подписок у выбывших мемберов - через час после синхронизации members_sync (03:00).
    REVOKE_CRON_HOUR: int = Field(4, alias="VPN_REVOKE_CRON_HOUR")
    REVOKE_CRON_MINUTE: int = Field(0, alias="VPN_REVOKE_CRON_MINUTE")
    REVOKE_CRON_TIMEZONE: str = Field("Europe/Moscow", alias="VPN_REVOKE_CRON_TIMEZONE")

    @field_validator("INBOUND_IDS", mode="before")
    @classmethod
    def split_inbound_ids(cls, value: str | list[int]) -> list[int]:
        if isinstance(value, str):
            return [int(item.strip()) for item in value.split(",") if item.strip()]
        return value

    @property
    def ENABLED(self) -> bool:
        """VPN-функциональность работает только при полностью заполненной секции."""
        return bool(self.BASE_URL and self.API_TOKEN and self.SUB_BASE_URL and self.INBOUND_IDS)


class LoggerConfig(_Section):
    SHOW_DEBUG_LOGS: bool = Field(False, alias="SHOW_DEBUG_LOGS")
    SHOW_DATETIME: bool = Field(False, alias="SHOW_DATETIME")
    DATETIME_FORMAT: str = Field("%Y-%m-%d %H:%M:%S", alias="DATETIME_FORMAT")
    TIME_IN_UTC: bool = Field(False, alias="TIME_IN_UTC")
    USE_COLORS_IN_CONSOLE: bool = Field(False, alias="USE_COLORS_IN_CONSOLE")
    LOG_TO_FILE: bool = Field(True, alias="LOG_TO_FILE")
    LOG_FILE_PATH: str = Field("logs/bot.log", alias="LOG_FILE_PATH")
    LOG_FILE_MAX_SIZE: int = Field(10 * 1024 * 1024, alias="LOG_FILE_MAX_SIZE")
    LOG_FILE_BACKUP_COUNT: int = Field(5, alias="LOG_FILE_BACKUP_COUNT")


class GlobalSettings(_Section):
    """Главный сборщик секций (pydantic сам вызывает фабрики, секции читают ``.env``)."""

    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)
    project: ProjectConfig = Field(default_factory=ProjectConfig)
    xui: XuiConfig = Field(default_factory=XuiConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)


# Инициализируем глобальный синглтон настроек
settings: Final[GlobalSettings] = GlobalSettings()
