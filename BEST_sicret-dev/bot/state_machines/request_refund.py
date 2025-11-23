from aiogram.fsm.state import StatesGroup, State


class RequestRefund(StatesGroup):
    MAIN_FORM = State()  # Главная форма с описанием и полями для ввода
    INPUT_NAME = State()  # Ввод имени
    INPUT_EVENT = State()  # Ввод мероприятия
    INPUT_REASON = State()  # Ввод причины
    INPUT_AMOUNT = State()  # Ввод суммы
    INPUT_CARD_NUMBER = State()  # Ввод номера карты
    REVIEW_FORM = State()  # Повторный показ для редактирования
    REVIEW_APPLICATION = State()  # Просмотр итогового варианта заявки
    CONFIRM_APPLICATION = State()  # Подтверждение отправки

