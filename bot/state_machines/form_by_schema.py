from aiogram.fsm.state import StatesGroup, State


class FormBySchema(StatesGroup):
    VIEW = State()  # Просмотр и навигация по форме
    ADD = State()  # Редактирование поля

