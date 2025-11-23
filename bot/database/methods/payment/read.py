from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.payment import Payment


async def get_payment_by_id(
    session: AsyncSession,
    payment_id: int,
) -> Optional[Payment]:
    """
    Получает платеж по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        payment_id: ID платежа

    Returns:
        Объект Payment или None, если не найден
    """
    stmt = select(Payment).where(Payment.id == payment_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

