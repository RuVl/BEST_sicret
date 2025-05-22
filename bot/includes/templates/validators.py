from abc import abstractmethod, ABC
from datetime import datetime
from typing import Any


class Validator(ABC):
	@abstractmethod
	def validate(self, value: Any) -> bool:
		pass


class DateValidator(Validator):
	def validate(self, value: Any) -> bool:
		try:
			datetime.strptime(value, '%d.%m.%Y')
			return True
		except ValueError:
			raise ValueError('format-type-incorrect')


class DummyValidator(Validator):
	def validate(self, value: Any) -> bool:
		return True  # Always True
