from typing import Any

from fluent.runtime import FluentLocalization

from includes.templates import get_validator, get_formatter
from utils import escape_mdv2
from .base_context import BaseContext


class PrimitiveContext(BaseContext):
	def __init__(self, schema: dict[str, str], parent: 'BaseContext' = None, required: bool = False):
		super().__init__(schema, parent, required)

		self.question = schema.get('question', f'Введите {self.description}:')
		self.question = escape_mdv2(self.question)

		if self.btn_name is None:
			self.btn_name = schema.get('description', 'No button name')

		self._value = schema.get('default')
		self._format = schema.get('format')

	def parse(self, value: str) -> Any:
		# Форматер преобразует ввод (например, из строки в число)
		formatter = get_formatter(self._type)
		value: Any = formatter.format(value)

		# Валидация правильности ввода (например, дата соответствует ДД.ММ.ГГГГ)
		validator = get_validator(self._format)
		if not validator.validate(value):
			raise ValueError('invalid-value')

		return value

	def set_value(self, parsed_value: Any):
		""" Вызывать только с результатом из parse метода! """
		self._value = parsed_value

	def get_value(self) -> Any:
		return self._value

	def clear(self):
		self._value = None

	def get_property(self, prop: Any) -> 'BaseContext':
		raise NotImplementedError('No inner context to view')

	def filled_required(self) -> bool:
		return self._value is not None if self.required else True

	def render_view(self, l10n: FluentLocalization) -> str:
		text = f'{self.description}: '
		if self._value is not None:
			text += f'`{self._value}`'
		return text

	def ask_question(self) -> str:
		return self.question
