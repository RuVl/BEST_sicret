from abc import ABC, abstractmethod
from typing import Any

from fluent.runtime import FluentLocalization

from utils import escape_mdv2


class BaseContext(ABC):
	__version__ = 1  # Версия контекста (для pickle) - изменить при изменении параметров

	BACK_ACTION = 'back'
	DELETE_ACTION = 'delete'

	def __init__(self, schema: dict[str, str], parent: 'BaseContext' = None, required: bool = False):
		self._type = schema.get('type')
		self._parent = parent
		self.required = required

		self.title = schema.get('title', 'No title')
		self.description = schema.get('description', 'No description')
		self.btn_name = schema.get('short_description')  # No need escape

		# Escape text
		self.title = escape_mdv2(self.title)
		self.description = escape_mdv2(self.description)

	@abstractmethod
	def get_value(self) -> Any:
		""" Возвращает текущее значение """
		pass

	@abstractmethod
	def clear(self):
		""" Clear all values """
		pass

	def delete_child(self, child: 'BaseContext'):
		""" Очистить значение ребенка """
		child.clear()

	@abstractmethod
	def get_property(self, prop: Any) -> 'BaseContext':
		"""
		Возвращает внутренний TemplateContext.
		Для array - по индексу (int), для object - по названию property
		"""
		pass

	@abstractmethod
	def filled_required(self) -> bool:
		""" Заполнены ли все обязательные поля """
		pass

	def can_generate(self) -> bool:
		""" Можно ли сгенерировать документ (все заполнено в главном контексте) """
		return self._parent is None and self.filled_required()

	def generate_context(self) -> dict:
		""" Генерирует контекст для Jinja на основе заполненных данных """
		if not self.can_generate():
			raise ValueError("Не все обязательные поля заполнены.")
		return self.get_value()

	@abstractmethod
	def render_view(self, l10n: FluentLocalization) -> str:
		""" Рендер текста """
		pass

	def render_data_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		""" Рендер клавиатуры для изменения данных. Формат: [(text, data)] """
		return []  # nothing

	def render_action_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		""" Рендер клавиатуры для действий (вперед, назад). Формат: [(text, action)] """
		if self._parent is not None:  # Если мы в подменю
			return [
				(l10n.format_value('back'), self.BACK_ACTION),
				(l10n.format_value('delete'), self.DELETE_ACTION)
			]
		return []

	def ask_question(self) -> str:
		raise NotImplementedError("Этот контекст не ожидает пользовательского ввода (не примитивный тип)")

	def view(self, data: str | int) -> 'BaseContext':
		""" Step forward to data from data_kb """
		return self.get_property(data)

	def do(self, action: str) -> 'BaseContext':
		""" Do action from action_kb """
		if action == self.BACK_ACTION:
			if self._parent is None:
				raise ValueError('Can not do a back action: parent is None')
			return self._parent
		elif action == self.DELETE_ACTION:
			if self._parent is None:
				raise ValueError('Can not do a delete action: parent is None')
			self._parent.delete_child(self)
			return self._parent

		raise NotImplementedError(f'Do {action=} is not implemented')

	def __getstate__(self):
		""" Сериализация """
		state = self.__dict__.copy()
		# Исключаем атрибуты, которые не нужно или нельзя сериализовать
		for attr in ['_abc_impl']:
			state.pop(attr, None)
		return state

	def __setstate__(self, state):
		""" Десериализация """
		self.__dict__.update(state)
