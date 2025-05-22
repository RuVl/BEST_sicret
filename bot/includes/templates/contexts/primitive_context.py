from typing import Any

from fluent.runtime import FluentLocalization

from includes.templates import get_validator, get_formatter
from .base_context import BaseContext


class PrimitiveContext(BaseContext):
	def __init__(self, schema: dict[str, str], parent: 'BaseContext' = None, required: bool = False):
		super().__init__(schema, parent, required)
		if self.btn_name is None:
			self.btn_name = schema.get('description', 'No button name')

		self._value = schema.get('default')
		self._format = schema.get('format')

	def set_value(self, value: Any):
		self.validate(new_value=value)
		formatter = get_formatter(self._format)
		self._value = formatter.format(value)

	def get_value(self) -> Any:
		return self._value

	def validate(self, new_value=None) -> bool:
		validator = get_validator(self._type)
		return validator.validate(self._value if new_value is None else new_value)

	def get_property(self, prop: Any) -> 'BaseContext':
		return None  # No inner context

	def filled(self) -> bool:
		return self._value is not None if self.required else True

	def render_view(self, l10n: FluentLocalization, **_) -> str:
		text = f'{self.description}: '
		if self.required:
			text = r'\* ' + text
		if self._value is not None:
			text += f'`{self._value}`'
		return text

	def render_data_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		return []  # nothing

	def render_action_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		if self._parent is not None:  # Если мы в подменю
			return [(l10n.format_value('back'), 'back')]
		return []  # Если мы в главном контексте

	def ask_question(self) -> str:
		return self.question

	def do(self, action: str | int):
		pass

	def view(self, data: str | int):
		pass
