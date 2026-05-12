from aiogram.fsm.state import State, StatesGroup


class CreateByApplyEquipment(StatesGroup):
    VIEW = State()
    INPUT_PROPERTY = State()
    SELECT_CATEGORY = State()
    SELECT_ITEM = State()
    INPUT_QUANTITY = State()
