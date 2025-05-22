from typing import Any

from fluent.runtime import FluentLocalization

from includes.templates import create_context
from .base_context import BaseContext


class ObjectContext(BaseContext):
	def __init__(self, schema: dict, parent: 'BaseContext' = None, required: bool = False):
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

	def validate(self) -> bool:
		return all(child.validate() for child in self._children.values())

	def get_children(self) -> dict:
		return self._children

	def get_property(self, prop: Any) -> 'BaseContext':
		return self._children.get(prop)

	def filled(self) -> bool:
		return all(
			not child.required or child.can_generate()
			for child in self._children.values()
		)

	def render_view(self, l10n: FluentLocalization, **kwargs) -> str:
		show_hint = kwargs.get('show_hint', True)

		parts = [f'*{self.title}*\n_{self.description}_\n']
		for key, child in self._children.items():
			parts.append(fr'\- {child.render_view(l10n, show_hint=False)}')

		result = '\n'.join(parts)
		if show_hint and filter(lambda child: child.required, self._children):
			result += '\n' + fr'_\* \- {l10n.format_value('required-hint')}_'

		return result

	def render_data_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		return list(map(self.property2button, self._children.items()))

	def render_action_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		if self._parent is not None:  # Если мы в подменю
			return [(l10n.format_value('back'), 'back')]
		return []  # Дефолт (в главном контексте, но еще не можем сгенерировать)

	@staticmethod
	def property2button(prop: tuple[str, 'BaseContext']) -> tuple[str, str | int]:
		""" Адаптер для кнопок для TemplateContext с type: object """
		key, child = prop
		text = child.btn_name
		if child.filled():
			text += ' ✅'
		return text, key

	def do(self, action: str | int):
		""" Do action from action_kb """
		match action:
			case 'back':
				pass
			case 'generate-document':
				pass
			
	def view(self, data: str | int):
		pass
