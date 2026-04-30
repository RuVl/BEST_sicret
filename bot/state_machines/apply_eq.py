from aiogram.fsm.state import StatesGroup, State


class CreateByApplyEquipment(StatesGroup):
    VIEW = State()
    ADD = State()

