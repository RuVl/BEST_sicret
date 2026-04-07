from aiogram.fsm.state import StatesGroup, State


class CreateByApplyEquipment(StatesGroup):
    CHOOSE_APPLY_EQUIPMENT = State()
    VIEW = State()  # User is viewing template
    ADD = State()  # User adds or changes template's data

