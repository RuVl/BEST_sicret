import json
from datetime import datetime
from typing import Any, Literal

from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fluent.runtime import FluentLocalization

from bot.keyboards.callback_factories import AskActionFactory
from bot.keyboards.common import paginate
from bot.utils import escape_mdv2


class CreateByTemplate(StatesGroup):
    CHOOSE = State()  # User selects template
    VIEW = State()  # User is viewing template
    ADD_PRIMITIVE = State()  # User adds or changes template's data


class TemplateContext:
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
        self.title: str = escape_mdv2(schema.get('title', schema.get('description', 'No title')))
        self.description: str = escape_mdv2(schema.get('description', 'No description'))
        self.short_description: str = schema.get('short_description', schema.get('description', 'No description'))  # No need escape
        self.question: str = escape_mdv2(schema.get('question')) or f'Введите {self.description}:'

        self._active_property_path = [] if parent is None else None  # Путь к активному элементу (есть только у корня)

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

    def set_value(self, value: Any, l10n: FluentLocalization):
        """ Устанавливает значение для примитивного типа. Выдает ValueError при ошибке валидации """

        if self._type == 'array':
            new_context = TemplateContext(self._item_scheme, parent=self, required=self.required)
            new_context.set_value(value, l10n)
            self._children.append(new_context)
        elif self._type == 'object':
            pass  # TODO хз
        else:
            self._value = self._validate_value(value, l10n)

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

    def get_value(self) -> Any:
        """ Возвращает текущее значение (или None) """

        if self._type == 'object':
            return {k: child.get_value() for k, child in self._children.items()}
        elif self._type == 'array':
            return [child.get_value() for child in self._children]
        else:
            return self._value

    def has_property(self, property_name: str) -> bool:
        return property_name in self._children if self._type == 'object' else None

    def get_property(self, property_name: str) -> 'TemplateContext':
        return self._children.get(property_name) if self._type == 'object' else None

    def get_active(self) -> 'TemplateContext':
        """ Возвращает текущий активный элемент """

        active = self
        for property_name in self._active_property_path:
            active = active.get_property(property_name)
        return active

    def forward(self, property_name: str) -> 'TemplateContext':
        """ Входит вглубь дерева, если элемента нет - ничего не делает """

        tc = self.get_active().get_property(property_name)
        if tc is not None:
            self._active_property_path.append(property_name)
        return tc

    def backward(self) -> 'TemplateContext':
        """ Возвращается к предыдущему свойству, если мы в корне - вернется None """

        if len(self._active_property_path) == 0:
            return None

        self._active_property_path.pop()
        return self.get_active()

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

    def render_context(self) -> dict:
        """ Генерирует контекст для Jinja на основе заполненных данных """

        if not self.can_render():
            raise ValueError("Не все обязательные поля заполнены.")
        return self.get_value()

    def render_view(self, l10n: FluentLocalization) -> str:
        """ Генерирует текст для отображения в чате Telegram """

        match self._type:
            case 'object':
                parts = [f'*{self.title}*\n_{self.description}_\n']
                for key, child in self._children.items():
                    parts.append(fr'\- {child.render_view(l10n)}')

                result = '\n'.join(parts)
                if self._parent is None and (self.required or filter(lambda child: child.required, self._children)):
                    result += '\n' + fr'_\* \- {l10n.format_value('required-hint')}_'

                return result
            case 'array':
                parts = [f'*{self.title}*\n_{self.description}_\n']
                for i, child in enumerate(self._children, 1):
                    parts.append(f'{i}. {child.render_view(l10n)}')

                return '\n'.join(parts)
            case _:
                return f'{'* ' if self.required else ''}{self.description}: `{self._value or ''}`'

    def add_child(self) -> 'TemplateContext':
        """ Добавляет новый элемент в массив, если это array """

        if self._type != 'array':
            raise ValueError('add_child можно вызывать только для массивов.')

        tc = TemplateContext(self._item_scheme, parent=self, required=self.required)
        self._children.append(tc)
        return tc

    def is_submenu(self) -> bool:
        """ Является ли контекст подменю (вложенные объекты) """

        return self._type in {'array', 'object'}

    def is_primitive(self) -> bool:
        """ Ожидает ли контекст пользовательского ввода """

        return not self.is_submenu()

    def ask_question(self) -> str:
        if not self.is_primitive():
            raise ValueError("Этот контекст не ожидает пользовательского ввода (не примитивный тип)")
        return self.question

    def render_keyboard(self, l10n: FluentLocalization, page: int = 0, cols: int = 2, rows: int = 5) -> InlineKeyboardMarkup:
        """ Генерирует клавиатуру для Telegram на основе текущего контекста """

        # Валидация
        if not (1 < rows < 9):
            raise ValueError('Строк не может быть меньше 1 или больше 9')

        if not (1 < cols < 5):
            raise ValueError('Столбцов не может быть меньше 1 или больше 5')

        # Для примитивных типов ничего не нужно рендерить
        if not self.is_submenu():
            return None

        if self._type == 'object':
            properties = [
                {
                    'name': key,
                    'type': child._type,
                    'text': f"{child.short_description} ✅" if child.can_render() else child.short_description
                }
                for key, child in self._children.items()
            ]

            # Адаптер для кнопок
            def property2button(prop: dict) -> InlineKeyboardButton:
                callback_data = AskActionFactory(data=prop['name'], type=prop['type']).pack()
                return InlineKeyboardButton(text=prop['text'], callback_data=callback_data)

            # Используем функцию пагинации
            keyboard = paginate(properties, page, property2button, prefix='props', cols=cols, rows=rows)

            # Проверяем обязательные поля
            if self.can_render():
                keyboard.row(
                    InlineKeyboardButton(
                        text=l10n.format_value('generate-document'),
                        callback_data='generate_document'
                    )
                )
            return keyboard.as_markup()

        elif self._type == "array":  # Клавиатура для массива
            keyboard = InlineKeyboardBuilder()

            # Кнопки для уже добавленных элементов массива
            for i, child in enumerate(self._children, 1):
                keyboard.add(
                    InlineKeyboardButton(
                        text=f'{l10n.format_value('array-item')} {i}',
                        callback_data=f'array_item:{i}'
                    )
                )

            # Кнопка для добавления нового элемента
            keyboard.row(
                InlineKeyboardButton(
                    text=l10n.format_value('add-item'),
                    callback_data='add_array_item'
                )
            )
            return keyboard.as_markup()

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
            else:
                context._children = list(map(
                    lambda child_data: cls.from_json(child_data, context),
                    raw.get('_children', [])
                ))

        return context
