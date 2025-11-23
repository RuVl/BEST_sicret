from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.person import Person


async def update_person(
    session: AsyncSession,
    person: Person,
    full_name: Optional[str] = None,
    payment_id: Optional[int] = None,
) -> Person:
    """
    Обновляет данные пользователя.

    Args:
        session: Асинхронная сессия SQLAlchemy
        person: Объект Person для обновления
        full_name: Новое полное имя (опционально)
        payment_id: Новый ID платежа (опционально)

    Returns:
        Обновленный объект Person
    """
    if full_name is not None:
        person.full_name = full_name
    if payment_id is not None:
        person.payment_id = payment_id
    
    await session.flush()
    await session.refresh(person)
    return person

