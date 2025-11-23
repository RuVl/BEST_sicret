from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.place import Place


async def update_place(
    session: AsyncSession,
    place: Place,
    address: Optional[str] = None,
    person_id: Optional[int] = None,
) -> Place:
    """
    Обновляет данные места хранения.

    Args:
        session: Асинхронная сессия SQLAlchemy
        place: Объект Place для обновления
        address: Новый адрес (опционально)
        person_id: Новый ID владельца (опционально)

    Returns:
        Обновленный объект Place
    """
    if address is not None:
        place.address = address
    if person_id is not None:
        place.person_id = person_id
    
    await session.flush()
    await session.refresh(place)
    return place





