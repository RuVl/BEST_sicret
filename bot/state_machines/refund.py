from aiogram.fsm.state import StatesGroup, State


class CreateRefundApply(StatesGroup):
    VIEW = State()  # Просмотр и подтверждение заявки
    EDIT = State()  # Редактирование выбранного поля
    ADD_BILL = State()  # Добавление чека
