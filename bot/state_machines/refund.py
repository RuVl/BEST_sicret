from aiogram.fsm.state import StatesGroup, State


class CreateByRefund(StatesGroup):
    VIEW = State()  # Просмотр и подтверждение заявки
    EDIT = State()  # Редактирование выбранного поля