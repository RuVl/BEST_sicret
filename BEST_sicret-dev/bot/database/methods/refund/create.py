from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.refund import Refund


async def create_refund(
    session: AsyncSession,
    name: str,
    customer_id: int,
    payment_id: int,
    description: Optional[str] = None,
) -> Refund:
    """
    Создает новый возврат в базе данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        name: Название товара
        customer_id: ID клиента
        payment_id: ID платежа
        description: Описание (опционально)

    Returns:
        Созданный объект Refund
    """
    refund = Refund(
        name=name,
        customer_id=customer_id,
        payment_id=payment_id,
        description=description,
    )
    session.add(refund)
    await session.flush()
    await session.refresh(refund)
    return refund

