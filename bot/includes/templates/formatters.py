from abc import ABC, abstractmethod
from typing import Any

from structlog import get_logger
from structlog.typing import FilteringBoundLogger

logger: FilteringBoundLogger = get_logger("templates.formatters")


class Formatter(ABC):
    @abstractmethod
    def format(self, value: str) -> Any:
        pass


class StringFormatter(Formatter):
    def format(self, value: str) -> str:
        return str(value)  # Nothing to do


class IntegerFormatter(Formatter):
    def format(self, value: str) -> int:
        try:
            return int(value)
        except ValueError as err:
            raise ValueError("invalid-integer-input") from err


class NumberFormatter(Formatter):
    def format(self, value: str) -> float:
        value = value.replace(",", ".")
        try:
            return float(value)
        except ValueError as err:
            raise ValueError("invalid-number-input") from err


class BooleanFormatter(Formatter):
    def format(self, value: str) -> bool:
        if value in ["Да", "Yes"]:
            return True
        elif value in ["Нет", "No"]:
            return False
        else:
            raise ValueError("invalid-boolean-input")


class DummyFormatter(Formatter):
    def __init__(self, formatter_type):
        if formatter_type:
            logger.warning(f"{formatter_type} not implemented!")

    def format(self, value: str) -> str:
        return value
