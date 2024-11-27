from enum import StrEnum, auto
from functools import lru_cache
from os import environ
from pathlib import Path
from tomllib import load
from typing import Type, TypeVar

from pydantic import BaseModel, field_validator, SecretStr

ConfigType = TypeVar("ConfigType", bound=BaseModel)


class BotConfig(BaseModel):
    __default_root_key__ = "bot"

    token: SecretStr
    owners: list


class TemplatesConfig(BaseModel):
    __default_root_key__ = "templates"

    root: Path


class LogRenderer(StrEnum):
    JSON = auto()
    CONSOLE = auto()


class LogConfig(BaseModel):
    __default_root_key__ = "logs"

    show_datetime: bool
    datetime_format: str
    show_debug_logs: bool
    time_in_utc: bool
    use_colors_in_console: bool
    renderer: LogRenderer

    @classmethod
    @field_validator('renderer', mode="before")
    def log_renderer_to_lower(cls, v: str):
        return v.lower()


@lru_cache
def parse_config_file() -> dict:
    """
    Gets the config by path from CONFIG_FILE_PATH or config.toml (by default).
    IMPORTANT: The function is cached. When you change the config, the bot must be restarted.
    """

    file_path = environ.get('CONFIG_FILE_PATH', default="config.toml")

    if file_path is None:
        raise ValueError("Could not find settings file")

    with open(file_path, "rb") as file:
        config_data = load(file)

    return config_data


@lru_cache
def get_config(model: Type[ConfigType], root_key: str = None) -> ConfigType:
    """
    Returns the required model with data by key.
    If the key is None, the model.__default_root_key__ is used.
    """

    if root_key is None:
        root_key = getattr(model, "__default_root_key__", None)

    config_dict = parse_config_file()
    if root_key not in config_dict:
        raise ValueError(f"Key {root_key} not found")

    return model.model_validate(config_dict[root_key])
