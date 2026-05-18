from aiogram.fsm.state import StatesGroup, State

class EquipmentAdd(StatesGroup):
    START = State()  # Начальное состояние - просмотр формы
    ADD = State()  # Ввод данных по полям
    SELECT_CATEGORY = State()  # Выбор категории
    CREATE_CATEGORY = State()  # Создание новой категории