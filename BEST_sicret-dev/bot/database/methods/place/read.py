from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.place import Place


async def get_place_by_id(
    session: AsyncSession,
    place_id: int,
) -> Optional[Place]:
    """
    Получает место хранения по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        place_id: ID места хранения

    Returns:
        Объект Place или None, если не найден
    """
    stmt = select(Place).where(Place.id == place_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()





