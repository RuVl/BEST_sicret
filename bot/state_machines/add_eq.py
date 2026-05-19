from aiogram.fsm.state import State, StatesGroup


class EquipmentAdd(StatesGroup):
    START = State()
    ADD = State()
    SELECT_CATEGORY = State()
    CREATE_CATEGORY = State()
    SELECT_PLACE = State()