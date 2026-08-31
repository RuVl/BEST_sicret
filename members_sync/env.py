"""Конфигурация сервиса через pydantic-settings (nested-паттерн, по аналогии с bot/env.py).

Настройки сгруппированы в подмодели-секции (``GoogleConfig``/``SyncConfig``/...), собранные на
едином ``Settings``. В отличие от бота каждая секция — самостоятельный ``BaseSettings``: pydantic
не наполняет вложенные ``BaseModel`` из плоских env по alias, поэтому секции читают ``.env`` сами.

Доступ: ``settings.google.SPREADSHEET_KEY``. Для совместимости со старыми импортами секции
дополнительно экспортируются под именами ``GoogleKeys``/``SyncKeys``/... (``SyncKeys.MODE`` и т.п.).

``.env`` берётся рядом с этим файлом; реальные переменные окружения (docker ``env_file``) имеют
приоритет над файлом.
"""

from pathlib import Path
from typing import Final

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_ENV_FILE = Path(__file__).resolve().parent / ".env"


class _Section(BaseSettings):
    """Базовая секция: единый источник ``.env`` и игнор лишних переменных."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )


class GoogleConfig(_Section):
    API_CREDENTIALS_FILE: str = Field("service_account.json", alias="API_CREDENTIALS_FILE")
    SPREADSHEET_KEY: str = Field(alias="SPREADSHEET_KEY")


class SyncConfig(_Section):
    WRITE_SHEET_NOTES: bool = Field(False, alias="WRITE_SHEET_NOTES")
    SHEET_NOTE_MARKER: str = Field("🤖 [sync]", alias="SHEET_NOTE_MARKER")
    AUTO_CREATE_SCHEMA: bool = Field(True, alias="AUTO_CREATE_SCHEMA")
    SYNC_REPORT_PATH: Path = Field(Path("last_sync_report.md"), alias="SYNC_REPORT_PATH")
    DUMP_JSON_PATH: Path = Field(Path("output/members.json"), alias="DUMP_JSON_PATH")


class RunConfig(_Section):
    MODE: str = Field("once", alias="RUN_MODE")
    CRON_HOUR: int = Field(3, alias="CRON_HOUR")
    CRON_MINUTE: int = Field(0, alias="CRON_MINUTE")
    CRON_TIMEZONE: str = Field("Europe/Moscow", alias="CRON_TIMEZONE")

    @field_validator("MODE")
    @classmethod
    def _lower(cls, value: str) -> str:
        return value.lower()


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


class LoggerConfig(_Section):
    DEBUG: bool = Field(False, alias="DEBUG")
    LOG_LEVEL: str = Field("DEBUG", alias="LOG_LEVEL")
    USE_COLORS_IN_CONSOLE: bool = Field(True, alias="USE_COLORS_IN_CONSOLE")

    LOG_TO_CONSOLE: bool = Field(True, alias="LOG_TO_CONSOLE")

    LOG_TO_FILE: bool = Field(True, alias="LOG_TO_FILE")
    LOG_FILE_PATH: str = Field("logs/members_sync.log", alias="LOG_FILE_PATH")
    LOG_FILE_MAX_SIZE: int = Field(10 * 1024 * 1024, alias="LOG_FILE_MAX_SIZE")
    LOG_FILE_BACKUP_COUNT: int = Field(5, alias="LOG_FILE_BACKUP_COUNT")

    LOG_TO_MD: bool = Field(True, alias="LOG_TO_MD")
    LOG_MD_PATH: str = Field("logs/warnings.md", alias="LOG_MD_PATH")
    LOG_MD_LEVEL: str = Field("WARNING", alias="LOG_MD_LEVEL")

    @field_validator("LOG_LEVEL", "LOG_MD_LEVEL")
    @classmethod
    def _upper(cls, value: str) -> str:
        return value.upper()


class Settings(_Section):
    """Главный сборщик секций (pydantic сам вызывает фабрики, секции читают ``.env``)."""

    google: GoogleConfig = Field(default_factory=GoogleConfig)
    sync: SyncConfig = Field(default_factory=SyncConfig)
    run: RunConfig = Field(default_factory=RunConfig)
    postgres: PostgresConfig = Field(default_factory=PostgresConfig)
    logger: LoggerConfig = Field(default_factory=LoggerConfig)


settings: Final[Settings] = Settings()

# Совместимость со старыми импортами: from env import SyncKeys / RunKeys / ...
GoogleKeys: Final[GoogleConfig] = settings.google
SyncKeys: Final[SyncConfig] = settings.sync
RunKeys: Final[RunConfig] = settings.run
PostgresKeys: Final[PostgresConfig] = settings.postgres
LoggerKeys: Final[LoggerConfig] = settings.logger
