from aiogram.fsm.state import StatesGroup, State


class ViewInventory(StatesGroup):
    CATEGORIES = State()  # Выбор категории
    ITEMS = State()       # Просмотр товаров