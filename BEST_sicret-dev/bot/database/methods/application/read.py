from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.application import Application


async def get_application_by_id(
    session: AsyncSession,
    application_id: int,
) -> Optional[Application]:
    """
    Получает заявку по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        application_id: ID заявки

    Returns:
        Объект Application или None, если не найден
    """
    stmt = select(Application).where(Application.id == application_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


