from aiogram.fsm.state import State, StatesGroup


class ViewVpnSubscription(StatesGroup):
    VIEW = State()  # Статус подписки: выпуск / ссылка / трафик
    AWG = State()  # Список устройств AmneziaWG + добавить
    AWG_DEVICE = State()  # Карточка устройства: статус, трафик, конфиг / переименовать / удалить
    AWG_NAME = State()  # Ввод названия: нового устройства или при переименовании
    AWG_CONFIG = State()  # Конфиг файлом или QR-кодом - сообщение исчезает при выходе и по таймеру
    AWG_DELETE = State()  # Подтверждение удаления устройства AmneziaWG
