class AwgError(Exception):
    """Веб-панель AmneziaWG вернула ошибку или недоступна."""


class AwgAuthError(AwgError):
    """API-токен не принят панелью (401/403)."""


class AwgPeerNotFoundError(AwgError):
    """Пира с таким ID в панели нет (или у него не найден конфиг)."""


class AwgDeviceLimitError(AwgError):
    """Все разрешённые устройства уже заведены."""


class AwgAccessRevokedError(AwgError):
    """Доступ отозван админом - заводить и выдавать ключи нельзя."""
