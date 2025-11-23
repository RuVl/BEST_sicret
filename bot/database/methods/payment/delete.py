from sqlalchemy.ext.asyncio import AsyncSession

from database.models.payment import Payment


async def delete_payment(
    session: AsyncSession,
    payment: Payment,
) -> None:
    """
    Удаляет платеж из базы данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        payment: Объект Payment для удаления
    """
    await session.delete(payment)
    await session.flush()

