from aiogram.fsm.state import State, StatesGroup


class CreateByApplyEquipment(StatesGroup):
    VIEW = State()
    INPUT_PROPERTY = State()
    INPUT_QUANTITY = State()
