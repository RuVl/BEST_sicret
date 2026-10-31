"""Асинхронный клиент панели 3x-ui (v3).

Авторизация - API-токен: ``Authorization: Bearer <token>``. При валидном токене панель
помечает запрос как ``api_authed`` и пропускает его мимо CSRF-мидлвари, поэтому ни логин,
ни cookie-сессия не нужны.

Все ответы приходят в конверте ``{"success": bool, "msg": str, "obj": any}``.
"""

from typing import TYPE_CHECKING, Any
from urllib.parse import quote

import aiohttp
import structlog
from structlog.typing import FilteringBoundLogger

from env import settings
from includes.vpn.exceptions import XuiAuthError, XuiClientNotFoundError, XuiError
from includes.vpn.schemas import ClientDetails, ClientRecord, ClientTraffic, XuiClientPayload

if TYPE_CHECKING:
    # includes.awg сам импортирует этот модуль - во время выполнения тип не нужен.
    from includes.awg.schemas import AwgClientPayload

logger: FilteringBoundLogger = structlog.get_logger("xui")

_API_PREFIX = "/panel/api"
_TIMEOUT = aiohttp.ClientTimeout(total=15)


def unwrap_envelope(payload: Any) -> Any:
    """Достать ``obj`` из конверта ответа панели, превратив ``success=false`` в исключение."""
    if not isinstance(payload, dict):
        raise XuiError("Панель вернула неожиданный формат ответа")

    if not payload.get("success", False):
        raise XuiError(payload.get("msg") or "Панель вернула ошибку без описания")

    return payload.get("obj")


class XuiClient:
    """Тонкая обёртка над REST-API панели. Держит одну сессию на всё время жизни бота."""

    def __init__(self, base_url: str, api_token: str, sub_base_url: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
        self._sub_base_url = sub_base_url.rstrip("/")
        self._session: aiohttp.ClientSession | None = None

    # === Инфраструктура ===

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self._api_token}"},
                timeout=_TIMEOUT,
            )
        return self._session

    async def close(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def _request(self, method: str, path: str, json: dict[str, Any] | None = None) -> Any:
        """Выполнить запрос и вернуть содержимое ``obj`` из конверта ответа."""
        session = await self._get_session()
        url = f"{self._base_url}{_API_PREFIX}{path}"

        try:
            async with session.request(method, url, json=json) as response:
                if response.status in (401, 403):
                    raise XuiAuthError("Панель не приняла API-токен")
                if response.status == 404:
                    raise XuiClientNotFoundError(f"Панель вернула 404 на {path}")

                # Панель на неавторизованный HTML-запрос отвечает не-JSON - не даём упасть в парсере.
                try:
                    payload = await response.json(content_type=None)
                except ValueError as exc:
                    raise XuiError(f"Некорректный ответ панели ({response.status})") from exc

        except aiohttp.ClientError as exc:
            raise XuiError(f"Панель недоступна: {exc}") from exc

        return unwrap_envelope(payload)

    # === Клиенты ===

    async def get_client_details(self, email: str) -> ClientDetails | None:
        """Клиент с его инбаундами и адресами в туннелях или ``None``, если клиента нет."""
        try:
            obj = await self._request("GET", f"/clients/get/{quote(email, safe='')}")
        except XuiClientNotFoundError:
            return None
        except XuiError as exc:
            # Панель на отсутствующего клиента отвечает success=false, а не 404.
            if "record not found" in str(exc).lower():
                return None
            raise

        if not obj or not obj.get("client"):
            return None
        return ClientDetails.model_validate(obj)

    async def get_client(self, email: str) -> ClientRecord | None:
        """Вернуть клиента панели или ``None``, если его нет."""
        details = await self.get_client_details(email)
        return ClientRecord.model_validate(details.client) if details else None

    async def get_traffic(self, email: str) -> ClientTraffic | None:
        obj = await self._request("GET", f"/clients/traffic/{quote(email, safe='')}")
        if obj is None:
            return None
        return ClientTraffic.model_validate(obj)

    async def get_links(self, email: str) -> list[str]:
        """Ссылки клиента во всех его инбаундах (``vless://``, ``vpn://``...) - то же, что в его подписке."""
        obj = await self._request("GET", f"/clients/links/{quote(email, safe='')}")
        if not isinstance(obj, list):
            raise XuiError(f"Панель вернула неожиданный список ссылок клиента {email}")
        return [link for link in obj if isinstance(link, str)]

    async def add_client(self, client: "XuiClientPayload | AwgClientPayload", inbound_ids: list[int]) -> None:
        """Завести клиента в инбаундах. Тело зависит от протокола: VLESS - ``XuiClientPayload``.

        Секреты, которых нет в теле, панель генерирует сама (у AmneziaWG - ключи и адрес в подсети).
        """
        await self._request(
            "POST",
            "/clients/add",
            json={
                "client": client.model_dump(by_alias=True),
                "inboundIds": inbound_ids,
            },
        )
        await logger.ainfo("xui-client-add", email=client.email, inbound_ids=inbound_ids)

    async def update_client(self, email: str, client: XuiClientPayload) -> None:
        """Перезаписать клиента.

        Панель не патчит строку, а заменяет её телом запроса, поэтому передавать нужно
        полного клиента - обычно ``ClientRecord.to_payload()`` с точечными правками.
        """
        await self._request(
            "POST",
            f"/clients/update/{quote(email, safe='')}",
            json=client.model_dump(by_alias=True),
        )
        await logger.ainfo("xui-client-update", email=email)

    async def set_enabled(self, email: str, enabled: bool) -> None:
        """Включить/выключить клиента, не тронув остальные его настройки."""
        record = await self.get_client(email)
        if record is None:
            raise XuiClientNotFoundError(f"Клиента {email} нет в панели")

        await self.update_client(email, record.to_payload().model_copy(update={"enable": enabled}))
        await logger.ainfo("xui-client-set-enabled", email=email, enabled=enabled)

    async def set_enabled_many(self, emails: list[str], enabled: bool) -> None:
        """Включить/выключить сразу нескольких клиентов. Тело клиента не пересылаем - ключи не трогаются."""
        if not emails:
            return
        path = "/clients/bulkEnable" if enabled else "/clients/bulkDisable"
        await self._request("POST", path, json={"emails": emails})
        await logger.ainfo("xui-clients-set-enabled", emails=emails, enabled=enabled)

    async def delete_client(self, email: str) -> None:
        """Удалить клиента из всех инбаундов вместе со счётчиками трафика."""
        await self._request("POST", f"/clients/del/{quote(email, safe='')}")
        await logger.ainfo("xui-client-delete", email=email)

    async def list_group_emails(self, group: str) -> list[str]:
        """Все email клиентов в группе - для сверки «БД бота ↔ панель»."""
        obj = await self._request("GET", f"/clients/groups/{quote(group, safe='')}/emails")
        return list(obj or [])

    # === Ссылка-подписка ===

    def build_subscription_url(self, sub_id: str) -> str:
        return f"{self._sub_base_url}/{sub_id}"


_client: XuiClient | None = None


def get_xui_client() -> XuiClient:
    """Синглтон клиента: одна сессия на процесс."""
    global _client
    if _client is None:
        _client = XuiClient(
            base_url=settings.xui.BASE_URL,
            api_token=settings.xui.API_TOKEN,
            sub_base_url=settings.xui.SUB_BASE_URL,
        )
    return _client


async def close_xui_client() -> None:
    if _client is not None:
        await _client.close()
