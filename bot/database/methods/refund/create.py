from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.refund import Refund


async def create_refund(
    session: AsyncSession,
    name: str,
    person_id: int,
    payment_id: Optional[int] = None,
    description: Optional[str] = None,
    event: Optional[str] = None,
    reason: Optional[str] = None,
    amount: Optional[float] = None,
    card_number: Optional[str] = None,
) -> Refund:
    """
    Создает новый возврат в базе данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        name: Название товара
        person_id: ID инициировавшего возврат (Person)
        payment_id: ID платежа (опционально)
        description: Описание (опционально)
        event: Событие, при котором произошел возврат (опционально)
        reason: Причина возврата (опционально)
        amount: Сумма возврата (опционально)
        card_number: Номер карты для возврата (опционально)

    Returns:
        Созданный объект Refund
    """
    refund = Refund(
        name=name,
        customer_id=person_id,
        payment_id=payment_id,
        description=description,
    )
    session.add(refund)
    await session.flush()
    await session.refresh(refund)
    return refund

