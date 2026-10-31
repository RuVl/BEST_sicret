"""Доменные операции над ключами AmneziaWG: устройства, выдача конфига, выключение.

Один ключ AmneziaWG - одно устройство: пир с одним ключом на двух устройствах сразу
перебивает endpoint, и связь рвётся на обоих. Поэтому человек заводит ключ (клиента
AmneziaWG-инбаунда в 3x-ui) на каждое устройство, в пределах лимита из разрешения.

Как и у VLESS, источник правды о ключе - панель: клиента могли удалить или выключить в её
админке, поэтому перед выдачей бот сверяется с ней и чинит расхождение сам. Так же переезжают
устройства со старого сервера AmneziaWG: клиента под их именем в 3x-ui нет, и бот заводит его
при первой выдаче конфига.
"""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from database.methods.awg_access import create_device, delete_device, mark_granted, mark_issued, set_device_label
from database.models import AwgAccess, AwgDevice, Person
from env import settings
from includes.awg.client import AwgClient
from includes.awg.exceptions import AwgAccessRevokedError, AwgDeviceLimitError, AwgError
from includes.awg.identity import build_peer_comment, device_client_name, free_device_number
from includes.awg.schemas import AwgPeer

logger: FilteringBoundLogger = structlog.get_logger("awg")


def _peer_comment(person: Person, device: AwgDevice) -> str:
    return build_peer_comment(person.full_name, person.telegram_username, person.telegram_id, device.number)


def _remark(device: AwgDevice) -> str:
    """Подпись над [Peer] в конфиге - по ней человек отличит файлы своих устройств."""
    return f"{settings.awg.TUNNEL_NAME} - {device.label or f'устройство {device.number}'}"


def device_limit(access: AwgAccess) -> int:
    """Лимит устройств: личный из разрешения или общий из настроек."""
    return access.device_limit if access.device_limit is not None else settings.awg.DEVICE_LIMIT


async def peers_by_name(client: AwgClient, access: AwgAccess) -> dict[str, AwgPeer]:
    """Ключи всех устройств разрешения в панели по имени клиента; отсутствующих в словаре нет."""
    return await client.find_peers([device.client_name for device in access.devices])


async def ensure_peer(client: AwgClient, device: AwgDevice, person: Person) -> AwgPeer:
    """Привести ключ устройства в рабочее состояние: создать, если его нет, и включить, если выключен."""
    peer = await client.find_peer(device.client_name)

    if peer is None:
        await client.create_peer(device.client_name, _peer_comment(person, device), person.telegram_id)
        peer = await client.find_peer(device.client_name)
        if peer is None:
            raise AwgError(f"Панель создала клиента {device.client_name}, но не отдаёт его")
        await logger.ainfo("awg-peer-created", person_id=person.id, client_name=device.client_name)

    if peer.disabled:
        await client.set_disabled([device.client_name], False)
        peer = peer.model_copy(update={"enable": True})
        await logger.ainfo("awg-peer-enabled", person_id=person.id, client_name=device.client_name)

    return peer


async def restore_access(session: AsyncSession, client: AwgClient, access: AwgAccess) -> None:
    """Доступ снова в силе (мембер вернулся в LBG или админ выдал повторно): включаем все ключи разом."""
    peers = await peers_by_name(client, access)
    await client.set_disabled([name for name, peer in peers.items() if peer.disabled], False)

    await mark_granted(session, access)
    await logger.ainfo("awg-access-restored", person_id=access.person_id)


async def _ensure_usable(session: AsyncSession, client: AwgClient, access: AwgAccess) -> None:
    """Общая проверка перед выдачей. Членство проверяет вызывающая сторона."""
    if access.status == "revoked":
        raise AwgAccessRevokedError("Доступ к AmneziaWG отозван админом")
    if access.status == "suspended":
        await restore_access(session, client, access)


async def issue_device_config(
    session: AsyncSession,
    client: AwgClient,
    access: AwgAccess,
    device: AwgDevice,
    person: Person,
) -> str:
    """Конфиг устройства для отправки человеку. Коммит - на вызывающей стороне."""
    await _ensure_usable(session, client, access)

    peer = await ensure_peer(client, device, person)
    config = await client.get_config(peer, _remark(device))

    await mark_issued(session, device)
    return config


async def add_device(
    session: AsyncSession,
    client: AwgClient,
    access: AwgAccess,
    person: Person,
    label: str | None = None,
) -> tuple[AwgDevice, str]:
    """Завести новое устройство и вернуть его конфиг. Коммит - на вызывающей стороне.

    Сначала строка в БД, потом пир: если коммит не доедет, следующий заход получит тот же
    свободный номер и то же имя клиента, а ``ensure_peer`` подхватит уже созданного пира.
    """
    await _ensure_usable(session, client, access)
    if len(access.devices) >= device_limit(access):
        raise AwgDeviceLimitError(f"Заведено {len(access.devices)} из {device_limit(access)} устройств")

    number = free_device_number(device.number for device in access.devices)
    device = await create_device(
        session, access, number=number, client_name=device_client_name(person.id, number), label=label
    )
    config = await issue_device_config(session, client, access, device, person)
    await logger.ainfo("awg-device-added", person_id=person.id, number=number)
    return device, config


async def rename_device(session: AsyncSession, device: AwgDevice, label: str) -> None:
    """Переименовать устройство - только в боте.

    Подпись клиента в панели не трогаем: 3x-ui на update не патчит клиента, а заменяет его телом
    запроса, и неполное тело перевыпустило бы ключи - конфиг на устройстве перестал бы работать.
    """
    await set_device_label(session, device, label)


async def remove_device(session: AsyncSession, client: AwgClient, access: AwgAccess, device: AwgDevice) -> None:
    """Удалить устройство: сначала пира в панели, потом строку - иначе ключ остался бы жить без учёта."""
    if await client.find_peer(device.client_name) is not None:
        await client.remove_peer(device.client_name)

    await delete_device(session, access, device)
    await logger.ainfo("awg-device-removed", person_id=access.person_id, number=device.number)


async def disable_peers(client: AwgClient, access: AwgAccess) -> int:
    """Выключить в панели ключи всех устройств. Возвращает, сколько ключей там нашлось."""
    peers = await peers_by_name(client, access)
    await client.set_disabled([name for name, peer in peers.items() if not peer.disabled], True)
    return len(peers)


async def remove_peers(session: AsyncSession, client: AwgClient, access: AwgAccess) -> int:
    """Удалить ключи всех устройств из панели и из БД. Возвращает, сколько устройств удалено."""
    devices = list(access.devices)
    for device in devices:
        await remove_device(session, client, access, device)
    return len(devices)
