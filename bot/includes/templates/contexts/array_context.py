from fluent.runtime import FluentLocalization

from .base_context import BaseContext


class ArrayContext(BaseContext):
	def __init__(self, schema: dict, parent: 'BaseContext' = None, required: bool = False):
		super().__init__(schema, parent, required)
		if self.btn_name is None:
			self.btn_name = schema.get('title', 'No button name')

		self.items_schema = schema['items']
		self._children = []

	def get_value(self) -> list:
		return [child.get_value() for child in self._children]

	def validate(self) -> bool:
		return all(child.validate() for child in self._children)

	def get_children(self) -> list:
		return self._children

	def get_property(self, prop: int) -> 'BaseContext':
		i = int(prop)
		return self._children[i] if 0 <= i < len(self._children) else None

	def filled(self) -> bool:
		if self.required and len(self._children) == 0:
			return False
		return all(child.can_generate() for child in self._children)

	def render_view(self, l10n: FluentLocalization, **kwargs) -> str:
		show_hint = kwargs.get('show_hint', True)

		parts = [f'*{self.title}*\n_{self.description}_']
		for i, child in enumerate(self._children, 1):
			parts.append(fr'{i}\. {child.render_view(l10n, show_hint=False)}')

		result = '\n\n'.join(parts)
		if show_hint and filter(lambda child: child.required, self._children):
			result += '\n' + fr'_\* \- {l10n.format_value('required-hint')}_'

		return result

	def render_data_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		return list(map(self.property2button, enumerate(self._children)))

	def render_action_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		keyboard = [
			(l10n.format_value('add-item'), 'add-item')
		]

		if self._parent is not None:  # Если мы в подменю
			keyboard.append((l10n.format_value('back'), 'back'))
			keyboard.append((l10n.format_value('delete'), 'delete'))

		return keyboard

	@staticmethod
	def property2button(prop: tuple[int, 'BaseContext']) -> tuple[str, str | int]:
		""" Адаптер для кнопок для TemplateContext с type: array """
		i, child = prop
		text = f'{i} - {child.btn_name}'
		if child.filled():
			text += ' ✅'
		return text, i

	def do(self, action: str | int):
		pass

	def view(self, data: str | int):
		pass
