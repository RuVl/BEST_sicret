"""Ключи AmneziaWG в панели 3x-ui: одно устройство - один клиент AmneziaWG-инбаунда.

Ходим в ту же панель и с тем же API-токеном, что и VLESS (``XuiClient``). Ключи и адрес
устройства панель генерирует сама при создании клиента, конфиг тоже собирает она; приватный
ключ бот видит только при выдаче конфига и нигде не хранит.

Ошибки панели (``XuiError``) отдаём наружу как ``AwgError`` - диалоги AmneziaWG ловят только их.
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import structlog
from structlog.typing import FilteringBoundLogger

from env import settings
from includes.awg.exceptions import AwgAuthError, AwgError
from includes.awg.schemas import AwgClientPayload, AwgPeer
from includes.awg.share_link import extract_device_config
from includes.vpn import XuiAuthError, XuiClient, XuiError, get_xui_client

logger: FilteringBoundLogger = structlog.get_logger("awg")


@contextmanager
def _panel_errors() -> Iterator[None]:
    try:
        yield
    except XuiAuthError as exc:
        raise AwgAuthError(str(exc)) from exc
    except XuiError as exc:
        raise AwgError(str(exc)) from exc


class AwgClient:
    """Операции над устройствами в одном AmneziaWG-инбаунде. Сессию держит общий ``XuiClient``."""

    def __init__(self, xui: XuiClient, inbound_id: int, group: str = "") -> None:
        self._xui = xui
        self._inbound_id = inbound_id
        self._group = group

    async def find_peer(self, client_name: str) -> AwgPeer | None:
        """Устройство по email клиента в панели или ``None``, если клиента нет."""
        with _panel_errors():
            details = await self._xui.get_client_details(client_name)
            if details is None:
                return None
            if self._inbound_id not in details.inbound_ids:
                # Клиента с таким email отвязали от инбаунда руками - создать заново не даст уникальность email.
                raise AwgError(f"Клиент {client_name} есть в панели, но не в AmneziaWG-инбаунде {self._inbound_id}")
            traffic = await self._xui.get_traffic(client_name)
        return AwgPeer.from_panel(details, self._inbound_id, traffic)

    async def find_peers(self, client_names: list[str]) -> dict[str, AwgPeer]:
        """Устройства по email разом - запросы к панели идут параллельно."""
        peers = await asyncio.gather(*(self.find_peer(name) for name in client_names))
        return {name: peer for name, peer in zip(client_names, peers, strict=True) if peer is not None}

    async def create_peer(self, client_name: str, comment: str, telegram_id: int) -> None:
        """Завести клиента: панель сама сгенерирует ключи и выдаст адрес из подсети инбаунда."""
        payload = AwgClientPayload(
            email=client_name,
            subId=uuid4().hex,
            tgId=telegram_id,
            comment=comment,
            group=self._group,
        )
        with _panel_errors():
            await self._xui.add_client(payload, [self._inbound_id])
        await logger.ainfo("awg-peer-create", client_name=client_name)

    async def get_config(self, peer: AwgPeer) -> str:
        """Текст клиентского ``.conf`` в том виде, в каком его собирает панель. Не логировать и не хранить."""
        with _panel_errors():
            links = await self._xui.get_links(peer.email)
        return extract_device_config(links, peer)

    async def set_disabled(self, client_names: list[str], disabled: bool) -> None:
        """Выключить/включить устройства: ключи и адреса остаются прежними."""
        with _panel_errors():
            await self._xui.set_enabled_many(client_names, not disabled)

    async def remove_peer(self, client_name: str) -> None:
        """Удалить клиента совсем: ключ перестаёт работать, адрес освобождается."""
        with _panel_errors():
            await self._xui.delete_client(client_name)
        await logger.ainfo("awg-peer-remove", client_name=client_name)


_client: AwgClient | None = None


def get_awg_client() -> AwgClient:
    """Синглтон поверх общего клиента 3x-ui - закрывать отдельно не нужно."""
    global _client
    if _client is None:
        _client = AwgClient(get_xui_client(), settings.awg.INBOUND_ID, settings.awg.GROUP)
    return _client
