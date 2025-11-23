from typing import Optional
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.payment import Payment


async def create_payment(
    session: AsyncSession,
    cost: int,
    is_paid: bool = False,
    bill: Optional[str] = None,
    payed_date: Optional[datetime] = None,
) -> Payment:
    """
    Создает новый платеж в базе данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        cost: Стоимость
        is_paid: Статус оплаты (по умолчанию False)
        bill: Ссылка на чек (опционально)
        payed_date: Дата фактической оплаты (опционально)

    Returns:
        Созданный объект Payment
    """
    payment = Payment(
        cost=cost,
        is_paid=is_paid,
        bill=bill,
        payed_date=payed_date,
    )
    session.add(payment)
    await session.flush()
    await session.refresh(payment)
    return payment

