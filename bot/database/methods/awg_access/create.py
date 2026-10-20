from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AwgAccess, AwgDevice


async def create_access(session: AsyncSession, *, person_id: int, device_limit: int | None = None) -> AwgAccess:
    """Выдать разрешение. Устройства человек заведёт сам в боте. Коммит - на вызывающей стороне."""
    access = AwgAccess(person_id=person_id, status="granted", device_limit=device_limit, devices=[])
    session.add(access)
    await session.flush()
    return access


async def create_device(
    session: AsyncSession,
    access: AwgAccess,
    *,
    number: int,
    client_name: str,
    label: str | None = None,
) -> AwgDevice:
    """Завести устройство под разрешением. Пир в панели создаёт вызывающая сторона."""
    device = AwgDevice(number=number, client_name=client_name, label=label)
    access.devices.append(device)
    await session.flush()
    return device
