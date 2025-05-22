from abc import ABC, abstractmethod
from typing import Any

from fluent.runtime import FluentLocalization

from utils import escape_mdv2


class BaseContext(ABC):
	__version__ = 1  # Версия контекста (для pickle)

	def __init__(self, schema: dict[str, str], parent: 'BaseContext' = None, required: bool = False):
		self._type = schema.get('type')
		self._parent = parent
		self.required = required

		self.title = schema.get('title', 'No title')
		self.description = schema.get('description', 'No description')
		self.question = schema.get('question', f'Введите {self.description}:')
		self.btn_name = schema.get('short_description')  # No need escape

		# Escape text
		self.title = escape_mdv2(self.title)
		self.description = escape_mdv2(self.description)
		self.question = escape_mdv2(self.question)

	@abstractmethod
	def get_value(self) -> Any:
		""" Возвращает текущее значение """
		pass

	@abstractmethod
	def validate(self) -> bool:
		""" Валидация значения. Возвращает bool или ValueError """
		pass

	@abstractmethod
	def get_property(self, prop: Any) -> 'BaseContext':
		"""
		Возвращает внутренний TemplateContext.
		Для array - по индексу (int), для object - по названию property
		"""
		pass

	@abstractmethod
	def filled(self) -> bool:
		""" Заполнены ли все обязательные поля """
		pass
	
	def can_generate(self) -> bool:
		""" Можно ли сгенерировать документ (все заполнено в главном контексте) """
		return self._parent is None and self.filled()

	def generate_context(self) -> dict:
		""" Генерирует контекст для Jinja на основе заполненных данных """
		if not self.can_generate():
			raise ValueError("Не все обязательные поля заполнены.")
		return self.get_value()

	@abstractmethod
	def render_view(self, l10n: FluentLocalization, **_) -> str:
		""" Рендер текста """
		pass

	@abstractmethod
	def render_data_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		""" Рендер клавиатуры для изменения данных. Формат: [(text, data)] """
		pass

	@abstractmethod
	def render_action_kb(self, l10n: FluentLocalization) -> list[tuple[str, str | int]]:
		""" Рендер клавиатуры для действий (вперед, назад, генерация). Формат: [(text, data)] """
		pass

	def ask_question(self) -> str:
		raise ValueError("Этот контекст не ожидает пользовательского ввода (не примитивный тип)")

	@abstractmethod
	def do(self, action: str | int):
		""" Do action from action_kb """
		pass
	
	@abstractmethod
	def view(self, data: str | int):
		""" Step forward to data from data_kb """
		pass

	def __getstate__(self):
		state = self.__dict__.copy()
		# Исключаем атрибуты, которые не нужно или нельзя сериализовать
		for attr in ['_abc_impl']:
			state.pop(attr, None)
		return state

	def __setstate__(self, state):
		self.__dict__.update(state)
