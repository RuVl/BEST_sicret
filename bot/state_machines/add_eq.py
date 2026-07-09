from aiogram.fsm.state import State, StatesGroup


class EquipmentAdd(StatesGroup):
    START = State()
    ADD = State()
    SELECT_CATEGORY = State()
    SELECT_PLACE = State()


class CategoryCreate(StatesGroup):
    INPUT_NAME = State()