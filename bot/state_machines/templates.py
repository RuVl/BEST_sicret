import json
from datetime import datetime
from typing import Any, Literal

from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fluent.runtime import FluentLocalization

from keyboards.callback_factories import AskDataFactory, ActionDataFactory
from keyboards.common import paginate
from utils import escape_mdv2


class CreateByTemplate(StatesGroup):
	CHOOSE_TEMPLATE = State()  # User selects template
	VIEW = State()  # User is viewing template
	ADD = State()  # User adds or changes template's data


class TemplateContext:
	# Complete
	def __init__(self, schema: dict, parent: 'TemplateContext' = None, required: bool = False):
		"""
		Инициализация контекста для jsonschema

		:param schema: JSON Schema элемента.
		:param required: Является ли элемент обязательным
		"""

		self._type: Literal['object', 'array', 'string', 'integer', 'number', 'null', 'boolean'] = schema.get('type', 'object')
		self._format: str = schema.get('format')
		self._item_scheme: str = schema.get('items')  # only for array
		self._parent: 'TemplateContext' = parent
		self._children: list['TemplateContext'] | dict[str, 'TemplateContext'] = None  # Вложенные контексты для объектов
		self._value: Any = None  # Значение, установленное пользователем (для примитивов)
		self._initialize_context(schema)

		self.required: bool = required  # Элемент обязателен
		self.title: str = schema.get('title', schema.get('description', 'No title'))
		self.description: str = schema.get('description', 'No description')
		self.short_description: str = schema.get(
			'short_description', self.title if self.is_submenu() else self.description
		)  # No need escape (button name)
		self.question: str = schema.get('question', f'Введите {self.description}:')

		self._active_property_path = [] if parent is None else None  # Путь к активному элементу (есть только у корня)

		# Escape text
		self.title = escape_mdv2(self.title)
		self.description = escape_mdv2(self.description)
		self.question = escape_mdv2(self.question)

	# Complete
	def _initialize_context(self, schema):
		""" Инициализирует дочерние контексты или примитивные значения """

		match self._type:
			case 'object':
				self._children = {}
				required = schema.get('required', [])
				for key, prop_schema in schema.get('properties', {}).items():
					self._children[key] = TemplateContext(prop_schema, parent=self, required=key in required)
			case 'array':
				self._children = []  # Для массива дети будут динамически добавляться
			case _:  # Для примитивных типов (string, integer, etc.)
				self._value = schema.get('default')

	# Partially complete
	def set_value(self, value: Any, l10n: FluentLocalization):
		""" Устанавливает значение для примитивного типа. Выдает ValueError при ошибке валидации """

		if self._type == 'array':  # костыль - это add_child
			new_context = TemplateContext(self._item_scheme, parent=self, required=self.required)
			new_context.set_value(value, l10n)
			self._children.append(new_context)
		elif self._type == 'object':
			pass  # и ничего не надо
		else:
			self._value = self._validate_value(value, l10n)

	# Complete
	def _validate_value(self, value: Any, l10n: FluentLocalization) -> str:
		""" Функция для валидации и форматирования пользовательских данных согласно format. Возвращает value или ошибку ValueError """

		value: str = value.strip()
		if not value:  # not empty
			raise ValueError(l10n.format_value('invalid-input'))

		match self._type:
			case 'integer':
				try:
					value = int(value)
				except ValueError:
					raise ValueError(l10n.format_value('input-type-incorrect', {'type': 'целое число'}))
			case 'number':
				try:
					value = float(value)
				except ValueError:
					raise ValueError(l10n.format_value('input-type-incorrect', {'type': 'рациональное число'}))
			case 'boolean':
				if value in ['Да', 'Yes']:
					value = True
				elif value in ['Нет', 'No']:
					value = False
				else:
					raise ValueError(l10n.format_value('invalid-boolean-input'))
			case 'string':
				pass

		match self._format:
			case 'date':
				try:
					datetime.strptime(value, '%d.%m.%Y')  # Try parse
				except ValueError:
					raise ValueError(l10n.format_value('format-type-incorrect'))

		return value

	# Complete
	def get_value(self) -> Any:
		""" Возвращает текущее значение (или None) """

		if self._type == 'object':
			return {k: child.get_value() for k, child in self._children.items()}
		elif self._type == 'array':
			return [child.get_value() for child in self._children]
		else:
			return self._value

	# Complete
	def get_property(self, property_name: str | int) -> 'TemplateContext':
		"""
		Возвращает внутренний TemplateContext.
		Для array - по индексу (int), для object - по названию property
		"""

		if self._type == 'array':
			i = int(property_name)
			return self._children[i] if 0 <= i < len(self._children) else None
		elif self._type == 'object':
			return self._children.get(property_name)
		else:
			return None

	def get_active(self) -> 'TemplateContext':
		""" Возвращает текущий активный элемент """

		if self._active_property_path is None:
			raise ValueError("Call get_active only for root (self) of TemplateContext")

		active = self
		for property_name in self._active_property_path:
			active = active.get_property(property_name)
		return active

	def forward(self, property_name: str | int) -> 'TemplateContext':
		""" Входит вглубь дерева, если элемента нет - ничего не делает """

		if self._active_property_path is None:
			raise ValueError("Call forward only for root (self) of TemplateContext")

		tc = self.get_active()
		ctx = tc.get_property(property_name)

		if ctx is not None:
			self._active_property_path.append(property_name)
		elif int(property_name) == -1 and tc._type == 'array':  # Добавляем новый элемент
			ctx = TemplateContext(tc._item_scheme, parent=tc, required=tc.required)
			tc._children.append(ctx)
			self._active_property_path.append(len(tc._children) - 1)

		return ctx

	def backward(self) -> 'TemplateContext':
		""" Возвращается к предыдущему свойству, если мы в корне - вернется None """

		if self._active_property_path is None:
			raise ValueError("Call backward only for root (self) of TemplateContext")

		if len(self._active_property_path) == 0:
			return None

		self._active_property_path.pop()
		return self.get_active()

	def delete_child(self) -> 'TemplateContext':
		""" Удаляет текущий активный элемент, если это элемент массива """

		if self._active_property_path is None:
			raise ValueError("Call delete_child only for root (self) of TemplateContext")

		ctx = self.get_active()
		if ctx._parent._type != 'array':
			raise ValueError("Can't delete non-array child")

		tc = self.backward()
		tc._children.remove(ctx)
		return tc

	# Complete
	def can_render(self) -> bool:
		""" Проверяет, заполнены ли все обязательные поля """

		if self._type == 'object':
			return all(
				not child.required or child.can_render()
				for child in self._children.values()
			)
		elif self._type == 'array':
			if self.required and len(self._children) == 0:
				return False

			return all(child.can_render() for child in self._children)
		else:
			return self._value is not None

	# Complete
	def render_context(self) -> dict:
		""" Генерирует контекст для Jinja на основе заполненных данных """

		if not self.can_render():
			raise ValueError("Не все обязательные поля заполнены.")
		return self.get_value()

	# Complete
	def render_view(self, l10n: FluentLocalization, show_hint=True) -> str:
		""" Генерирует текст для отображения в чате Telegram """

		match self._type:
			case 'object':
				parts = [f'*{self.title}*\n_{self.description}_\n']
				for key, child in self._children.items():
					parts.append(fr'\- {child.render_view(l10n, show_hint=False)}')

				result = '\n'.join(parts)
			case 'array':
				parts = [f'*{self.title}*\n_{self.description}_']
				for i, child in enumerate(self._children, 1):
					parts.append(fr'{i}\. {child.render_view(l10n, show_hint=False)}')

				result = '\n\n'.join(parts)
			case _:
				text = f'{self.description}: '
				if self.required:
					text = r'\* ' + text
				if self._value is not None:
					text += f'`{self._value}`'
				return text

		if show_hint and filter(lambda child: child.required, self._children):
			result += '\n' + fr'_\* \- {l10n.format_value('required-hint')}_'

		return result

	# Complete
	def render_keyboard(self, l10n: FluentLocalization, page: int = 0, cols: int = 2, rows: int = 5) -> InlineKeyboardMarkup:
		""" Генерирует клавиатуру для Telegram на основе текущего контекста """

		# Валидация
		if not (1 < rows < 9):
			raise ValueError('Строк не может быть меньше 1 или больше 9')

		if not (1 < cols < 5):
			raise ValueError('Столбцов не может быть меньше 1 или больше 5')

		if self.is_primitive():  # Для примитивных типов ничего особенного
			keyboard = InlineKeyboardBuilder()
		elif self._type == 'object':
			def property2button(prop: tuple[str, 'TemplateContext']) -> InlineKeyboardButton:
				""" Адаптер для кнопок для TemplateContext с type: object """

				key, child = prop
				text = child.short_description
				if child.can_render():
					text += ' ✅'
				callback_data = AskDataFactory(key=key, parent_type='object').pack()
				return InlineKeyboardButton(text=text, callback_data=callback_data)

			keyboard = paginate(self._children.items(), page, property2button, prefix='props', cols=cols, rows=rows)
		elif self._type == 'array':  # Клавиатура для массива
			def property2button(prop: tuple[int, 'TemplateContext']) -> InlineKeyboardButton:
				""" Адаптер для кнопок для TemplateContext с type: array """

				i, child = prop
				text = f'{i} - {child.short_description}'
				if child.can_render():
					text += ' ✅'
				callback_data = AskDataFactory(key=i, parent_type='array').pack()
				return InlineKeyboardButton(text=text, callback_data=callback_data)

			keyboard = paginate(enumerate(self._children), page, property2button, prefix='props', cols=cols, rows=rows)

			# Кнопка для добавления нового элемента
			keyboard.row(
				InlineKeyboardButton(
					text=l10n.format_value('add-item'),
					callback_data=AskDataFactory(key=-1, parent_type='array').pack()  # -1 - добавление элемента
				)
			)

		if self._parent is None and self.can_render():  # Если мы в главном контексте и можем сгенерировать документ
			keyboard.row(InlineKeyboardButton(
				text=l10n.format_value('generate-document'),
				callback_data=ActionDataFactory(action='generate-document').pack()
			))
		elif self._parent is not None:  # Если мы в подменю
			keyboard.row(InlineKeyboardButton(
				text=l10n.format_value('back'),
				callback_data=ActionDataFactory(action='back').pack()
			))
			if self._parent._type == 'array':  # Если мы элемент массива
				keyboard.row(InlineKeyboardButton(
					text=l10n.format_value('delete'),
					callback_data=ActionDataFactory(action='delete').pack()
				))

		return keyboard.as_markup()

	# Complete
	def is_submenu(self) -> bool:
		""" Является ли контекст подменю (вложенные объекты) """

		return self._type in {'array', 'object'}

	# Complete
	def is_primitive(self) -> bool:
		""" Ожидает ли контекст пользовательского ввода """

		return not self.is_submenu()

	# Complete
	def ask_question(self) -> str:
		if not self.is_primitive():
			raise ValueError("Этот контекст не ожидает пользовательского ввода (не примитивный тип)")
		return self.question

	def to_json(self) -> str:
		""" Сериализует контекст в строку JSON """

		data = self.__dict__.copy()

		# Filter None values
		data = {k: v for k, v in data.items() if v is not None}
		data.pop('_parent', None)  # remove the backward link

		if self.is_submenu():
			data['_children'] = {
				key: child.to_json()
				for key, child in self._children.items()
			} if self._type == 'object' else list(map(lambda child: child.to_json(), self._children))

		return json.dumps(data)

	@classmethod
	def from_json(cls, data: str, parent: 'TemplateContext' = None) -> 'TemplateContext':
		""" Создает TemplateContext из JSON строки """

		raw = json.loads(data)
		context = cls({}, parent=parent, required=raw.get('required'))

		# Set all properties
		for key, value in raw.items():
			setattr(context, key, value)

		# Set children for sub_menu types
		if context.is_submenu():
			if context._type == 'object':
				context._children = {
					key: cls.from_json(child_data, context)
					for key, child_data in (raw.get('_children', {})).items()
				}
			elif context._type == 'array':
				context._children = list(map(
					lambda child_data: cls.from_json(child_data, context),
					raw.get('_children', [])
				))

		return context
