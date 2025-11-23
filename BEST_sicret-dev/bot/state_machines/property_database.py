from aiogram.fsm.state import StatesGroup, State


class PropertyDatabase(StatesGroup):
    MAIN_MENU = State()  # Главное меню с информацией и двумя кнопками
    SHOW_LIST_CATEGORY = State()  # Выбор категории для просмотра списка
    SHOW_LIST_ITEMS = State()  # Отображение таблицы имущества выбранной категории
    CREATE_APPLICATION = State()  # Форма создания заявки
    INPUT_NAME = State()  # Ввод имени
    INPUT_PURPOSE = State()  # Ввод цели
    SELECT_ITEMS = State()  # Выбор категории для выбора предметов
    SELECT_ITEMS_FROM_CATEGORY = State()  # Выбор предметов из категории
    REVIEW_APPLICATION = State()  # Просмотр итоговой заявки
    CONFIRM_APPLICATION = State()  # Подтверждение отправки

