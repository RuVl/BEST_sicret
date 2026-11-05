"""Панель 3x-ui через py3xui: общий клиент API и то, что библиотека оставляет на стороне бота.

Запросы, модели и исключения - библиотечные. Здесь только решения бота: один клиент на процесс
без повторов запросов, неуспех отдельных клиентов в bulk-ответе как ошибка и текст ошибки без секретов.
"""

import httpx
import structlog
from py3xui import AsyncApi, BulkResult, XuiApiError
from pydantic import ValidationError
from structlog.typing import FilteringBoundLogger

from env import settings

logger: FilteringBoundLogger = structlog.get_logger("xui")

_TIMEOUT_SECONDS = 15
# Повтор POST после таймаута попал бы в уже выполненное действие: удаление вернуло бы «клиента нет».
_ATTEMPTS = 1

# XuiApiError, pydantic.ValidationError и JSONDecodeError (HTML вместо JSON) - наследники ValueError.
PANEL_ERRORS: tuple[type[Exception], ...] = (ValueError, httpx.HTTPError)

_api: AsyncApi | None = None


def get_xui_api() -> AsyncApi:
    """Клиент API панели, один на процесс: закрывать нечего, соединение открывается на каждый запрос."""
    global _api
    if _api is None:
        _api = AsyncApi(settings.xui.BASE_URL, token=settings.xui.API_TOKEN, timeout=_TIMEOUT_SECONDS)
        _api.max_retries = _ATTEMPTS
    return _api


def panel_error_text(exc: Exception) -> str:
    """Текст ошибки панели для логов и сводок.

    В ``str(ValidationError)`` попадают входные значения, а среди них бывают ключи клиента, поэтому
    берём только пути полей. У ``httpx.ReadTimeout`` и подобных ``str()`` может быть пустым.
    """
    if isinstance(exc, ValidationError):
        fields = ", ".join(".".join(map(str, error["loc"])) or "obj" for error in exc.errors())
        return f"Панель вернула {exc.title} не по схеме: {fields}"
    if isinstance(exc, XuiApiError):
        return exc.msg or "Панель вернула ошибку без описания"
    if isinstance(exc, httpx.HTTPStatusError):
        return f"Панель ответила HTTP {exc.response.status_code}"
    return str(exc) or type(exc).__name__


def raise_for_skipped(result: BulkResult) -> None:
    """Пропущенный клиент - неуспех именно этого клиента: панель на него отвечает ``success=true``."""
    if result.skipped:
        skipped = "; ".join(f"{skip.email} ({skip.reason})" for skip in result.skipped)
        raise XuiApiError(f"Панель пропустила клиентов: {skipped}")


async def set_clients_enabled(api: AsyncApi, emails: list[str], enabled: bool) -> None:
    """Включить или выключить клиентов, не пересылая их тело: ключи и настройки не трогаются.

    Пропущенный клиент - ошибка: иначе джоб пометил бы его отключённым, а ключ продолжил бы работать.
    Остальных панель к этому моменту уже переключила, повтор их не затронет.
    """
    if not emails:
        return
    result = await (api.client.bulk_enable if enabled else api.client.bulk_disable)(emails)
    raise_for_skipped(result)
    await logger.ainfo("xui-clients-set-enabled", emails=emails, enabled=enabled)
