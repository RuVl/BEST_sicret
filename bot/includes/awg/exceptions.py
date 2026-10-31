class AwgError(Exception):
    """Панель 3x-ui вернула ошибку или недоступна, либо AmneziaWG-инбаунд настроен не так."""


class AwgAuthError(AwgError):
    """API-токен не принят панелью (401/403)."""


class AwgDeviceLimitError(AwgError):
    """Все разрешённые устройства уже заведены."""


class AwgAccessRevokedError(AwgError):
    """Доступ отозван админом - заводить и выдавать ключи нельзя."""
