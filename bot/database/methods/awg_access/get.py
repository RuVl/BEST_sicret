from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import AwgAccess, AwgDevice, Person


async def get_access_by_person(session: AsyncSession, person_id: int) -> AwgAccess | None:
    """Разрешение человека на AmneziaWG (не более одного) вместе с устройствами или ``None``."""
    return await session.scalar(select(AwgAccess).where(AwgAccess.person_id == person_id))


async def get_device_by_client_name(session: AsyncSession, client_name: str) -> AwgDevice | None:
    """Устройство по email его клиента в панели - чтобы два человека не получили одно имя."""
    return await session.scalar(select(AwgDevice).where(AwgDevice.client_name == client_name))


async def list_accesses(session: AsyncSession) -> list[AwgAccess]:
    """Все разрешения вместе с владельцем и его членством - для админского списка."""
    query = (
        select(AwgAccess)
        .options(joinedload(AwgAccess.person).joinedload(Person.lbg_member))
        .order_by(AwgAccess.granted_at)
    )
    return list(await session.scalars(query))
