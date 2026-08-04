"""Асинхронный клиент панели 3x-ui (v3).

Авторизация - API-токен: ``Authorization: Bearer <token>``. При валидном токене панель
помечает запрос как ``api_authed`` и пропускает его мимо CSRF-мидлвари, поэтому ни логин,
ни cookie-сессия не нужны.

Все ответы приходят в конверте ``{"success": bool, "msg": str, "obj": any}``.
"""

from typing import Any
from urllib.parse import quote

import aiohttp
import structlog
from structlog.typing import FilteringBoundLogger

from env import settings
from includes.vpn.exceptions import XuiAuthError, XuiClientNotFoundError, XuiError
from includes.vpn.schemas import ClientRecord, ClientTraffic, XuiClientPayload

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

    async def get_client(self, email: str) -> ClientRecord | None:
        """Вернуть клиента панели или ``None``, если его нет."""
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
        return ClientRecord.model_validate(obj["client"])

    async def get_traffic(self, email: str) -> ClientTraffic | None:
        obj = await self._request("GET", f"/clients/traffic/{quote(email, safe='')}")
        if obj is None:
            return None
        return ClientTraffic.model_validate(obj)

    async def add_client(self, client: XuiClientPayload, inbound_ids: list[int]) -> None:
        await self._request(
            "POST",
            "/clients/add",
            json={
                "client": client.model_dump(by_alias=True),
                "inboundIds": inbound_ids,
            },
        )
        await logger.ainfo("xui-client-add", email=client.email, inbound_ids=inbound_ids)

    async def set_enabled(self, email: str, enabled: bool) -> None:
        """Включить/выключить клиента.

        Панель принимает только полное тело ``model.Client``, поэтому сначала читаем
        текущего клиента: иначе перезатрём настройки, выставленные в панели руками.
        """
        record = await self.get_client(email)
        if record is None:
            raise XuiClientNotFoundError(f"Клиента {email} нет в панели")

        payload = record.to_payload().model_copy(update={"enable": enabled})
        await self._request(
            "POST",
            f"/clients/update/{quote(email, safe='')}",
            json=payload.model_dump(by_alias=True),
        )
        await logger.ainfo("xui-client-set-enabled", email=email, enabled=enabled)

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
