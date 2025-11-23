from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.payment import Payment


async def update_payment(
    session: AsyncSession,
    payment: Payment,
    cost: Optional[int] = None,
    is_paid: Optional[bool] = None,
    bill: Optional[str] = None,
    payed_date: Optional[datetime] = None,
) -> Payment:
    """
    Обновляет данные платежа.

    Args:
        session: Асинхронная сессия SQLAlchemy
        payment: Объект Payment для обновления
        cost: Новая стоимость (опционально)
        is_paid: Новый статус оплаты (опционально)
        bill: Новая ссылка на чек (опционально)
        payed_date: Новая дата фактической оплаты (опционально)

    Returns:
        Обновленный объект Payment
    """
    if cost is not None:
        payment.cost = cost
    if is_paid is not None:
        payment.is_paid = is_paid
    if bill is not None:
        payment.bill = bill
    if payed_date is not None:
        payment.payed_date = payed_date
    
    await session.flush()
    await session.refresh(payment)
    return payment

