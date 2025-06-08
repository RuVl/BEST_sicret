from typing import Any

from fluent.runtime import FluentLocalization

from includes.templates import create_context
from .base_context import BaseContext


class ObjectContext(BaseContext):
	def __init__(self, schema: dict, parent: BaseContext = None, required: bool = False):
		super().__init__(schema, parent, required)
		if self.btn_name is None:
			self.btn_name = schema.get('title', 'No button name')

		required = schema.get('required', [])
		self._children = {
			key: create_context(prop_schema, self, required=key in required)
			for key, prop_schema in schema.get('properties', {}).items()
		}

	def get_value(self) -> dict:
		return {key: child.get_value() for key, child in self._children.items()}

	def clear(self):
		for child in self._children.values():
			child.clear()

	def get_property(self, prop: Any) -> BaseContext:
		return self._children.get(prop)

	def filled_required(self) -> bool:
		return all(
			child.filled_required()
			for child in self._children.values()
		)

	def render_view(self, l10n: FluentLocalization) -> str:
		parts = [f'*{self.title}*\n_{self.description}_\n']
		for key, child in self._children.items():
			parts.append(fr'\-{r' \*' if child.required else ''} {child.render_view(l10n)}')
		return '\n'.join(parts)

	def render_data_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		return list(map(self.property2button, self._children.items()))

	@staticmethod
	def property2button(prop: tuple[str, BaseContext]) -> tuple[str, str | int]:
		""" Адаптер для кнопок для TemplateContext с type: object """
		key, child = prop
		text = child.btn_name
		if child.filled_required() and child.get_value() is not None:
			text += ' ✅'
		return text, key
