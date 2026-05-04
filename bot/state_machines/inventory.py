from aiogram.fsm.state import StatesGroup, State


class ViewInventory(StatesGroup):
    SELECT_CATEGORY = State()  # Выбор категории
    SELECT_ITEM = State()  # Просмотр списка товаров
    VIEW_ITEM = State()  # Детали товара
