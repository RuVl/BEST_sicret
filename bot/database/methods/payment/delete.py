from sqlalchemy.ext.asyncio import AsyncSession

from database.models.payment import Payment


async def delete_payment(
    session: AsyncSession,
    payment: Payment,
) -> None:
    """
    Удаляет платеж из базы данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        payment: Объект Payment для удаления
    """
    session.delete(payment)
    await session.flush()

