from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Place


async def get_places(session: AsyncSession) -> list[Place]:
    result = await session.execute(select(Place).order_by(Place.id))
    return list(result.scalars().all())


async def get_place_by_id(session: AsyncSession, place_id: int) -> Place | None:
    result = await session.execute(
        select(Place).where(Place.id == place_id)
    )
    return result.scalar_one_or_none()