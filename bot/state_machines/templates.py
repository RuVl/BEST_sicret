from aiogram.fsm.state import StatesGroup, State


class CreateByTemplate(StatesGroup):
    CHOOSE = State()  # User selects template
    VIEW = State()  # User is viewing template
    ADD = State()  # User adds or changes template's data
