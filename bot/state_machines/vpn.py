from aiogram.fsm.state import State, StatesGroup


class ViewVpnSubscription(StatesGroup):
    VIEW = State()  # Статус подписки: выпуск / ссылка / трафик
