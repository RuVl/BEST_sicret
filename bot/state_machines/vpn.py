from aiogram.fsm.state import State, StatesGroup


class ViewVpnSubscription(StatesGroup):
    VIEW = State()  # Статус подписки: выпуск / ссылка / трафик
    AWG = State()  # Устройства AmneziaWG: добавить / конфиг / удалить
    AWG_DELETE = State()  # Подтверждение удаления устройства AmneziaWG
