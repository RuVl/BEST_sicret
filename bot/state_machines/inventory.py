from aiogram.fsm.state import StatesGroup, State


class ViewInventory(StatesGroup):
    VIEW_CATEGORIES = State()  # Выбор категории
    VIEW_ITEMS = State()       # Просмотр товаров