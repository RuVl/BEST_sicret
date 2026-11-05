class AwgError(Exception):
    """Панель 3x-ui вернула ошибку или недоступна, либо AmneziaWG-инбаунд настроен не так."""


class AwgDeviceLimitError(AwgError):
    """Все разрешённые устройства уже заведены."""


class AwgAccessRevokedError(AwgError):
    """Доступ отозван админом - заводить и выдавать ключи нельзя."""
