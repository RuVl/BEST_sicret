from aiogram.fsm.state import State, StatesGroup


class CreateRefundApply(StatesGroup):
    VIEW = State()  # Просмотр и подтверждение заявки
    EDIT = State()  # Редактирование выбранного поля
    ADD_BILL = State()  # Добавление чека
