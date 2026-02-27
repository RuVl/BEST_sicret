from sqlalchemy.ext.asyncio import AsyncSession

from database.models.place import Place


async def create_place(
    session: AsyncSession,
    address: str,
    person_id: int,
) -> Place:
    """
    Создает новое место хранения в базе данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        address: Адрес места хранения
        person_id: ID владельца места

    Returns:
        Созданный объект Place
    """
    place = Place(
        address=address,
        person_id=person_id,
    )
    session.add(place)
    await session.flush()
    await session.refresh(place)
    return place





