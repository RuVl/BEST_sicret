from pathlib import Path
from typing import Final

from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# --- ПОДБОРКИ НАСТРОЕК (Обычные модели Pydantic) ---
class TelegramConfig(BaseModel):
    API_TOKEN: str = Field(alias="TG_API_TOKEN")
    PRESIDENT_ID: int = 0
    TREASURER_ID: int = 0


class PostgresConfig(BaseModel):
    HOST: str = Field("localhost", alias="POSTGRES_HOST")
    PORT: str = Field("5432", alias="POSTGRES_PORT")
    USER: str = Field("postgres", alias="POSTGRES_USER")
    PASSWORD: str = Field("", alias="POSTGRES_PASSWORD")
    DATABASE: str = Field("database", alias="POSTGRES_DB")

    @property
    def URL(self) -> str:
        return f"postgresql+asyncpg://{self.USER}:{self.PASSWORD}@{self.HOST}:{self.PORT}/{self.DATABASE}"


class RedisConfig(BaseModel):
    USE_REDIS: bool = Field(True, alias="USE_REDIS")
    HOST: str = Field("localhost", alias="REDIS_HOST")
    PORT: str = Field("6379", alias="REDIS_PORT")
    DATABASE: str = Field("0", alias="REDIS_DB")

    @property
    def URL(self) -> str:
        return f"redis://{self.HOST}:{self.PORT}/{self.DATABASE}"


class ProjectConfig(BaseModel):
    DEBUG: bool = Field(alias="DEBUG")
    RESOURCE_DIR: Path = Field(Path("resources/"), alias="RESOURCE_DIR")
    TEMPLATES_DIR: Path = Field(Path("resources/templates/"), alias="TEMPLATES_DIR")
    REFUND_BILLS_DIR: Path = Field(
        Path("resources/refund_bills/"), alias="REFUND_BILLS_DIR"
    )
    LOCALE_DIR: Path = Field(Path("l10n/"), alias="LOCALE_DIR")
    AVAILABLE_LOCALES: list[str] = Field(["ru"], alias="AVAILABLE_LOCALES")

    # Динамическая сборка путей, если они не заданы в .env явно, а зависят от RESOURCE_DIR
    @model_validator(mode="before")
    @classmethod
    def assemble_paths(cls, data: dict) -> dict:
        # Извлекаем RESOURCE_DIR, учитывая дефолтное значение
        resource_dir_raw = data.get("RESOURCE_DIR", "resources/")
        resource_dir = (
            Path(resource_dir_raw)
            if isinstance(resource_dir_raw, str)
            else resource_dir_raw
        )

        if "TEMPLATES_DIR" not in data:
            data["TEMPLATES_DIR"] = resource_dir / "templates/"
        if "REFUND_BILLS_DIR" not in data:
            data["REFUND_BILLS_DIR"] = resource_dir / "refund_bills/"
        return data


class LoggerConfig(BaseModel):
    SHOW_DEBUG_LOGS: bool = Field(False, alias="SHOW_DEBUG_LOGS")
    SHOW_DATETIME: bool = Field(False, alias="SHOW_DATETIME")
    DATETIME_FORMAT: str = Field("%Y-%m-%d %H:%M:%S", alias="DATETIME_FORMAT")
    TIME_IN_UTC: bool = Field(False, alias="TIME_IN_UTC")
    USE_COLORS_IN_CONSOLE: bool = Field(False, alias="USE_COLORS_IN_CONSOLE")
    LOG_TO_FILE: bool = Field(True, alias="LOG_TO_FILE")
    LOG_FILE_PATH: str = Field("logs/bot.log", alias="LOG_FILE_PATH")
    LOG_FILE_MAX_SIZE: int = Field(10 * 1024 * 1024, alias="LOG_FILE_MAX_SIZE")
    LOG_FILE_BACKUP_COUNT: int = Field(5, alias="LOG_FILE_BACKUP_COUNT")


# --- ГЛАВНЫЙ КЛАСС-СБОРЩИК (Управляет загрузкой .env) ---
# https://pydantic.dev/docs/validation/latest/concepts/pydantic_settings/
class GlobalSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # игнорирует другие переменные в окружении
    )

    # Pydantic сам заполнит переменные данными по alias-именам из env
    telegram: TelegramConfig = Field(
        default_factory=lambda: TelegramConfig.model_validate({})
    )
    postgres: PostgresConfig = Field(
        default_factory=lambda: PostgresConfig.model_validate({})
    )
    redis: RedisConfig = Field(default_factory=lambda: RedisConfig.model_validate({}))
    project: ProjectConfig = Field(
        default_factory=lambda: ProjectConfig.model_validate({})
    )
    logger: LoggerConfig = Field(
        default_factory=lambda: LoggerConfig.model_validate({})
    )


# Инициализируем глобальный синглтон настроек
settings: Final[GlobalSettings] = GlobalSettings()
