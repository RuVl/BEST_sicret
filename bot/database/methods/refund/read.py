from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.refund import Refund


async def get_refund_by_id(
    session: AsyncSession,
    refund_id: int,
) -> Optional[Refund]:
    """
    Получает возврат по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        refund_id: ID возврата

    Returns:
        Объект Refund или None, если не найден
    """
    stmt = select(Refund).where(Refund.id == refund_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

