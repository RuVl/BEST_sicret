"""Ключи AmneziaWG в панели 3x-ui: одно устройство - один клиент AmneziaWG-инбаунда.

Ходим в ту же панель и с тем же API-токеном, что и VLESS (``get_xui_api``). Ключи и адрес
устройства панель генерирует сама при создании клиента, конфиг тоже собирает она; приватный
ключ бот видит только при выдаче конфига и нигде не хранит.

Ошибки панели отдаём наружу как ``AwgError`` - диалоги AmneziaWG ловят только их.
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import structlog
from py3xui import AsyncApi, Client
from structlog.typing import FilteringBoundLogger

from env import settings
from includes.awg.exceptions import AwgAuthError, AwgError
from includes.awg.schemas import DEFAULT_KEEPALIVE, AwgPeer
from includes.awg.share_link import extract_device_config
from includes.vpn import PANEL_ERRORS, get_xui_api, is_auth_error, panel_error_text, set_clients_enabled

logger: FilteringBoundLogger = structlog.get_logger("awg")


@contextmanager
def _panel_errors() -> Iterator[None]:
    try:
        yield
    except PANEL_ERRORS as exc:
        error = AwgAuthError if is_auth_error(exc) else AwgError
        raise error(panel_error_text(exc)) from exc


class AwgClient:
    """Операции над устройствами в одном AmneziaWG-инбаунде."""

    def __init__(self, api: AsyncApi, inbound_id: int, group: str = "") -> None:
        self._api = api
        self._inbound_id = inbound_id
        self._group = group

    async def find_peer(self, client_name: str) -> AwgPeer | None:
        """Устройство по email клиента в панели или ``None``, если клиента нет."""
        with _panel_errors():
            details = await self._api.client.get_details(client_name)
            if details is None:
                return None
            if self._inbound_id not in details.inbound_ids:
                # Клиента с таким email отвязали от инбаунда руками - создать заново не даст уникальность email.
                raise AwgError(f"Клиент {client_name} есть в панели, но не в AmneziaWG-инбаунде {self._inbound_id}")
            traffic = await self._api.client.get_traffic(client_name)
        return AwgPeer.from_panel(details, self._inbound_id, traffic)

    async def has_client(self, client_name: str) -> bool:
        """Есть ли клиент с таким email в панели - один запрос, без счётчиков трафика."""
        with _panel_errors():
            return await self._api.client.get_details(client_name) is not None

    async def find_peers(self, client_names: list[str]) -> dict[str, AwgPeer]:
        """Устройства по email разом - запросы к панели идут параллельно."""
        peers = await asyncio.gather(*(self.find_peer(name) for name in client_names))
        return {name: peer for name, peer in zip(client_names, peers, strict=True) if peer is not None}

    async def create_peer(self, client_name: str, comment: str, telegram_id: int) -> None:
        """Завести клиента: панель сама сгенерирует ключи и выдаст адрес из подсети инбаунда.

        Ключей и адреса в теле нет намеренно. Лимиты VLESS устройству не нужны: один ключ и так работает
        только на одном устройстве. Повторный вызов с тем же email ключи не перевыпускает.
        """
        client = Client(
            email=client_name,
            enable=True,
            sub_id=uuid4().hex,
            tg_id=telegram_id,
            comment=comment,
            group=self._group,
            keep_alive=DEFAULT_KEEPALIVE,
        )
        with _panel_errors():
            await self._api.client.add(self._inbound_id, [client])
        await logger.ainfo("awg-peer-create", client_name=client_name)

    async def get_config(self, peer: AwgPeer) -> str:
        """Текст клиентского ``.conf`` в том виде, в каком его собирает панель. Не логировать и не хранить."""
        with _panel_errors():
            links = await self._api.client.get_links(peer.email)
        return extract_device_config(links, peer)

    async def set_disabled(self, client_names: list[str], disabled: bool) -> None:
        """Выключить/включить устройства: ключи и адреса остаются прежними."""
        with _panel_errors():
            await set_clients_enabled(self._api, client_names, not disabled)

    async def remove_peer(self, client_name: str) -> None:
        """Удалить клиента совсем: ключ перестаёт работать, адрес освобождается."""
        with _panel_errors():
            await self._api.client.delete(self._inbound_id, client_name)
        await logger.ainfo("awg-peer-remove", client_name=client_name)


_client: AwgClient | None = None


def get_awg_client() -> AwgClient:
    """Синглтон поверх общего клиента 3x-ui - закрывать отдельно не нужно."""
    global _client
    if _client is None:
        _client = AwgClient(get_xui_api(), settings.awg.INBOUND_ID, settings.awg.GROUP)
    return _client
