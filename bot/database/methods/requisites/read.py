from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.requisites import Requisites


async def get_requisites_by_id(
    session: AsyncSession,
    requisites_id: int,
) -> Optional[Requisites]:
    """
    Получает реквизиты по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        requisites_id: ID реквизитов

    Returns:
        Объект Requisites или None, если не найден
    """
    stmt = select(Requisites).where(Requisites.id == requisites_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
