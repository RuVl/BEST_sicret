from fluent.runtime import FluentLocalization

from .base_context import BaseContext


class ArrayContext(BaseContext):
	ADD_ITEM = 'add-item'

	def __init__(self, schema: dict, parent: BaseContext = None, required: bool = False):
		super().__init__(schema, parent, required)
		if self.btn_name is None:
			self.btn_name = schema.get('title', 'No button name')

		self.items_schema = schema['items']
		self._children: list[BaseContext] = []

	def get_value(self) -> list:
		return [child.get_value() for child in self._children]

	def clear(self):
		self._children.clear()

	def delete_child(self, child: BaseContext):
		self._children.remove(child)

	def get_property(self, prop: int) -> BaseContext:
		i = int(prop)
		return self._children[i] if 0 <= i < len(self._children) else None

	def filled_required(self) -> bool:
		if self.required and len(self._children) == 0:
			return False
		return all(child.filled_required() for child in self._children)

	def render_view(self, l10n: FluentLocalization) -> str:
		parts = [f'*{self.title}*\n_{self.description}_']
		for i, child in enumerate(self._children, 1):
			# В ArrayContext требуется следить за required
			parts.append(fr'{i}\. {child.render_view(l10n)}')
		return '\n\n'.join(parts)

	def render_data_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		return list(map(self.property2button, enumerate(self._children)))

	@staticmethod
	def property2button(prop: tuple[int, BaseContext]) -> tuple[str, str | int]:
		""" Адаптер для кнопок для TemplateContext с type: array """
		i, child = prop
		text = f'{i} - {child.btn_name}'
		if child.filled_required() and child.get_value() is not None:
			text += ' ✅'
		return text, i

	def render_action_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		keyboard = [
			(l10n.format_value('add-item'), self.ADD_ITEM)
		]

		if self._parent is not None:  # Если мы в подменю
			keyboard.append((l10n.format_value('back'), self.BACK_ACTION))
			keyboard.append((l10n.format_value('delete'), self.DELETE_ACTION))

		return keyboard

	def do(self, action: str):
		if action == self.ADD_ITEM:
			from includes.templates import create_context
			# По дефолту - все дети ArrayContext не required
			# Но хотя бы один ребенок требуется, если self.required
			child = create_context(self.items_schema, self, False)
			self._children.append(child)
			return child

		return super().do(action)
