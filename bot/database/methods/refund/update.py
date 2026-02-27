from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.refund import Refund


async def update_refund(
    session: AsyncSession,
    refund: Refund,
    name: Optional[str] = None,
    description: Optional[str] = None,
    customer_id: Optional[int] = None,
    payment_id: Optional[int] = None,
) -> Refund:
    """
    Обновляет данные возврата.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        refund: Объект Refund для обновления
        name: Новое название товара (опционально)
        description: Новое описание (опционально)
        customer_id: Новый ID клиента (опционально)
        payment_id: Новый ID платежа (опционально)

    Returns:
        Обновленный объект Refund
    """
    if name is not None:
        refund.name = name
    if description is not None:
        refund.description = description
    if customer_id is not None:
        refund.customer_id = customer_id
    if payment_id is not None:
        refund.payment_id = payment_id
    
    await session.flush()
    await session.refresh(refund)
    return refund





