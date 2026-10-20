"""Доменные операции над ключом AmneziaWG: выдача конфига и выключение.

Как и у VLESS, источник правды о ключе - панель: пира могли удалить или выключить в её
админке, поэтому перед каждой выдачей бот сверяется с ней и чинит расхождение сам.
В БД бота - только имя клиента и решение админа (``granted/suspended/revoked``).
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from database.methods.awg_access import mark_granted, mark_issued
from database.models import AwgAccess, Person
from includes.awg.client import AwgClient
from includes.awg.exceptions import AwgError
from includes.awg.identity import build_peer_comment
from includes.awg.schemas import AwgPeer

logger: FilteringBoundLogger = structlog.get_logger("awg")


async def ensure_peer(client: AwgClient, access: AwgAccess, person: Person) -> AwgPeer:
    """Привести пира в рабочее состояние: создать, если его нет, и включить, если выключен."""
    peer = await client.find_peer(access.client_name)

    if peer is None:
        comment = build_peer_comment(person.full_name, person.telegram_username, person.telegram_id)
        await client.create_peer(access.client_name, comment)
        peer = await client.find_peer(access.client_name)
        if peer is None:
            raise AwgError(f"Панель создала клиента {access.client_name}, но не показывает его в списке")
        await logger.ainfo("awg-peer-created", person_id=person.id, client_name=access.client_name)

    if peer.disabled:
        await client.set_disabled(peer.id, False)
        await logger.ainfo("awg-peer-enabled", person_id=person.id, client_name=access.client_name)

    if not peer.has_config:
        # Пир заведён в обход установщика (конфига в каталоге клиентов нет) - отдать нечего.
        raise AwgError(f"У клиента {access.client_name} нет конфига в панели")

    return peer


async def issue_config(session: AsyncSession, client: AwgClient, access: AwgAccess, person: Person) -> str:
    """Конфиг для отправки человеку. Членство проверяет вызывающая сторона, коммит - тоже.

    ``suspended`` здесь значит, что мембер вернулся в LBG: доступ оживает сам,
    а ``revoked`` (решение админа) сюда попадать не должен.
    """
    if access.status == "revoked":
        raise AwgError(f"Доступ {access.client_name} отозван админом")

    peer = await ensure_peer(client, access, person)
    config = await client.get_config(peer.id)

    if access.status == "suspended":
        await mark_granted(session, access)
        await logger.ainfo("awg-access-restored", person_id=person.id)
    await mark_issued(session, access)
    return config


async def disable_peer(client: AwgClient, access: AwgAccess) -> bool:
    """Выключить пира в панели. ``False`` - пира там нет, выключать нечего."""
    peer = await client.find_peer(access.client_name)
    if peer is None:
        return False
    if not peer.disabled:
        await client.set_disabled(peer.id, True)
    return True
