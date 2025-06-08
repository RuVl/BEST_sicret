from abc import abstractmethod, ABC
from typing import Any


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
		except ValueError:
			raise ValueError('invalid-integer-input')


class NumberFormatter(Formatter):
	def format(self, value: str) -> float:
		try:
			return float(value)
		except ValueError:
			raise ValueError('invalid-number-input')


class BooleanFormatter(Formatter):
	def format(self, value: str) -> bool:
		if value in ['Да', 'Yes']:
			return True
		elif value in ['Нет', 'No']:
			return False
		else:
			raise ValueError('invalid-boolean-input')


class DummyFormatter(Formatter):
	def format(self, value: str) -> str:
		# TODO warning message
		return value
