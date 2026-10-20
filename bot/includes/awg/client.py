"""Асинхронный клиент веб-панели AmneziaWG (amneziawg-web).

Авторизация - ``Authorization: Bearer <token>`` (``AUTH_API_TOKEN`` панели); токен действует
только на ``/api/*``. Пира панель создаёт сама (генерирует ключи и правит ``awg0.conf``),
поэтому приватный ключ клиента бот видит только внутри отдаваемого конфига и нигде не хранит.
"""

from typing import Any

import aiohttp
import structlog
from structlog.typing import FilteringBoundLogger

from env import settings
from includes.awg.exceptions import AwgAuthError, AwgError, AwgPeerNotFoundError
from includes.awg.schemas import AwgPeer

logger: FilteringBoundLogger = structlog.get_logger("awg")

# Создание пира ждёт syncconf на интерфейсе - запас больше, чем у 3x-ui.
_TIMEOUT = aiohttp.ClientTimeout(total=30)


class AwgClient:
    """Тонкая обёртка над REST-API панели. Держит одну сессию на всё время жизни бота."""

    def __init__(self, base_url: str, api_token: str) -> None:
        self._base_url = base_url.rstrip("/")
        self._api_token = api_token
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

    async def _request(self, method: str, path: str, json: Any = None, *, as_text: bool = False) -> Any:
        """Выполнить запрос к ``/api{path}``: JSON (или текст при ``as_text``) либо исключение."""
        session = await self._get_session()
        url = f"{self._base_url}/api{path}"

        try:
            async with session.request(method, url, json=json) as response:
                if response.status in (401, 403):
                    raise AwgAuthError("Панель AmneziaWG не приняла API-токен")

                if response.status >= 400:
                    message = await _error_message(response)
                    if response.status == 404:
                        raise AwgPeerNotFoundError(message)
                    raise AwgError(message)

                if as_text:
                    return await response.text()
                try:
                    return await response.json(content_type=None)
                except ValueError as exc:
                    raise AwgError(f"Некорректный ответ панели AmneziaWG ({response.status})") from exc

        except aiohttp.ClientError as exc:
            raise AwgError(f"Панель AmneziaWG недоступна: {exc}") from exc

    # === Пиры ===

    async def list_peers(self) -> list[AwgPeer]:
        obj = await self._request("GET", "/peers")
        return [AwgPeer.model_validate(item) for item in obj or []]

    async def find_peer(self, client_name: str) -> AwgPeer | None:
        """Пир по имени клиента установщика (``friendly_name``) или ``None``."""
        for peer in await self.list_peers():
            if peer.friendly_name == client_name:
                return peer
        return None

    async def create_peer(self, client_name: str, comment: str) -> None:
        """Завести клиента: панель сама выберет IP, сгенерирует ключи и применит конфиг."""
        await self._request("POST", "/admin/users", json={"name": client_name, "comment": comment})
        await logger.ainfo("awg-peer-create", client_name=client_name)

    async def get_config(self, peer_id: int) -> str:
        """Текст клиентского ``.conf``. Внутри приватный ключ - не логировать и не хранить."""
        return await self._request("GET", f"/peers/{peer_id}/config", as_text=True)

    async def set_disabled(self, peer_id: int, disabled: bool) -> None:
        """Выключить/включить пира: панель сразу снимает его с интерфейса или возвращает."""
        await self._request("PATCH", f"/peers/{peer_id}", json={"disabled": disabled})
        await logger.ainfo("awg-peer-set-disabled", peer_id=peer_id, disabled=disabled)

    async def remove_peer(self, peer_id: int) -> None:
        """Удалить пира совсем (ключи и конфиг). Пустое JSON-тело панель требует от CSRF."""
        await self._request("POST", f"/admin/users/{peer_id}/remove", json={})
        await logger.ainfo("awg-peer-remove", peer_id=peer_id)


async def _error_message(response: aiohttp.ClientResponse) -> str:
    """Текст ошибки из ``{"error": ...}``, а если тело не JSON - статус."""
    try:
        payload = await response.json(content_type=None)
    except ValueError:
        payload = None
    if isinstance(payload, dict) and payload.get("error"):
        return str(payload["error"])
    return f"Панель AmneziaWG ответила {response.status}"


_client: AwgClient | None = None


def get_awg_client() -> AwgClient:
    """Синглтон клиента: одна сессия на процесс."""
    global _client
    if _client is None:
        _client = AwgClient(base_url=settings.awg.BASE_URL, api_token=settings.awg.API_TOKEN)
    return _client


async def close_awg_client() -> None:
    if _client is not None:
        await _client.close()
