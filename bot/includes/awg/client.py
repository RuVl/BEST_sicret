"""Ключи AmneziaWG в панели 3x-ui: одно устройство - один клиент AmneziaWG-инбаунда.

Ходим в ту же панель и с тем же API-токеном, что и VLESS (``XuiClient``). Ключи и адрес
устройства панель генерирует сама при создании клиента; приватный ключ бот видит только
при сборке конфига и нигде не хранит.

Ошибки панели (``XuiError``) отдаём наружу как ``AwgError`` - диалоги AmneziaWG ловят только их.
"""

import asyncio
from collections.abc import Iterator
from contextlib import contextmanager
from uuid import uuid4

import structlog
from structlog.typing import FilteringBoundLogger

from env import settings
from includes.awg.config import build_client_config
from includes.awg.exceptions import AwgAuthError, AwgError
from includes.awg.schemas import AwgClientPayload, AwgInbound, AwgPeer
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

    def __init__(self, xui: XuiClient, inbound_id: int, endpoint_host: str = "") -> None:
        self._xui = xui
        self._inbound_id = inbound_id
        self._endpoint_host = endpoint_host

    async def find_peer(self, client_name: str) -> AwgPeer | None:
        """Устройство по email клиента в панели или ``None``, если клиента нет."""
        with _panel_errors():
            obj = await self._xui.get_client_obj(client_name)
            if obj is None:
                return None
            if self._inbound_id not in (obj.get("inboundIds") or []):
                # Клиента с таким email отвязали от инбаунда руками - создать заново не даст уникальность email.
                raise AwgError(f"Клиент {client_name} есть в панели, но не в AmneziaWG-инбаунде {self._inbound_id}")
            traffic = await self._xui.get_traffic(client_name)
        return AwgPeer.from_panel(obj, self._inbound_id, traffic)

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
            group=settings.awg.GROUP,
        )
        with _panel_errors():
            await self._xui.add_client(payload, [self._inbound_id])
        await logger.ainfo("awg-peer-create", client_name=client_name)

    async def get_config(self, peer: AwgPeer, remark: str = "") -> str:
        """Текст клиентского ``.conf``. Внутри приватный ключ - не логировать и не хранить."""
        with _panel_errors():
            inbound = AwgInbound.from_panel(await self._xui.get_inbound(self._inbound_id))
        if inbound.protocol and inbound.protocol != "amneziawg":
            raise AwgError(f"Инбаунд {self._inbound_id} - не AmneziaWG, а {inbound.protocol}")

        # Без явного адреса - Listen IP инбаунда. Домен панели не годится: он за Cloudflare, а тот не пускает UDP.
        host = self._endpoint_host or inbound.listen
        if not host or host in ("0.0.0.0", "::"):
            raise AwgError("Не задан адрес сервера для Endpoint: укажите Listen IP инбаунда или AWG_ENDPOINT_HOST")
        return build_client_config(peer, inbound, host, remark)

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
        _client = AwgClient(get_xui_client(), settings.awg.INBOUND_ID, settings.awg.ENDPOINT_HOST)
    return _client
