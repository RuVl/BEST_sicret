from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from structlog import get_logger
from structlog.typing import FilteringBoundLogger

logger: FilteringBoundLogger = get_logger("templates.validators")


class Validator(ABC):
    @abstractmethod
    def validate(self, value: Any) -> bool:
        pass


class DateValidator(Validator):
    def validate(self, value: str) -> bool:
        try:
            datetime.strptime(value, "%d.%m.%Y")
            return True
        except ValueError:
            return False
            raise ValueError("invalid-type")


class DummyValidator(Validator):
    def __init__(self, format_name: str):
        if format_name:
            logger.warning(f"{format_name} not implemented!")

    def validate(self, value: Any) -> bool:
        return True  # Always True
