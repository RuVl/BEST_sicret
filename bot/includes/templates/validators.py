from abc import abstractmethod, ABC
from datetime import datetime
from typing import Any


class Validator(ABC):
	@abstractmethod
	def validate(self, value: Any) -> bool:
		pass


class DateValidator(Validator):
	def validate(self, value: str) -> bool:
		try:
			datetime.strptime(value, '%d.%m.%Y')
			return True
		except ValueError:
			raise ValueError('invalid-type')


class DummyValidator(Validator):
	def validate(self, value: Any) -> bool:
		return True  # Always True
