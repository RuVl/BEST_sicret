from aiogram.fsm.state import State, StatesGroup


class ViewInventory(StatesGroup):
    SELECT_CATEGORY = State()  # Выбор категории
    SELECT_ITEM = State()  # Просмотр списка товаров
    VIEW_ITEM = State()  # Детали товара
