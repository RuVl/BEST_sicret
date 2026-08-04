from aiogram.fsm.state import State, StatesGroup


class ViewProfile(StatesGroup):
    VIEW = State()  # Карточка профиля с навигацией
