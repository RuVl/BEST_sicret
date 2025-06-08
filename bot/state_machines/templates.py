from aiogram.fsm.state import StatesGroup, State


class CreateByTemplate(StatesGroup):
	CHOOSE_TEMPLATE = State()  # User selects template
	VIEW = State()  # User is viewing template
	ADD = State()  # User adds or changes template's data
