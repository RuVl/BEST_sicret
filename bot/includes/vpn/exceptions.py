class XuiError(Exception):
    """Панель 3x-ui вернула ошибку или недоступна."""


class XuiAuthError(XuiError):
    """API-токен не принят панелью (401/403)."""


class XuiClientNotFoundError(XuiError):
    """Клиента с таким email в панели нет."""
