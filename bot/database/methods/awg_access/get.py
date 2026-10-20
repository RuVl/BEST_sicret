from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import AwgAccess, Person


async def get_access_by_person(session: AsyncSession, person_id: int) -> AwgAccess | None:
    """Разрешение человека на AmneziaWG (не более одного) или ``None``."""
    return await session.scalar(select(AwgAccess).where(AwgAccess.person_id == person_id))


async def get_access_by_client_name(session: AsyncSession, client_name: str) -> AwgAccess | None:
    """Разрешение по имени клиента - чтобы не выдать одно имя двоим."""
    return await session.scalar(select(AwgAccess).where(AwgAccess.client_name == client_name))


async def list_accesses(session: AsyncSession) -> list[AwgAccess]:
    """Все разрешения вместе с владельцем и его членством - для админского списка."""
    query = (
        select(AwgAccess)
        .options(joinedload(AwgAccess.person).joinedload(Person.lbg_member))
        .order_by(AwgAccess.granted_at)
    )
    return list(await session.scalars(query))
