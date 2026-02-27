from sqlalchemy.ext.asyncio import AsyncSession

from database.models.person import Person


async def create_person(
        session: AsyncSession,
        telegram_id: int,
        full_name: str,
) -> Person:
    """
    Создает нового пользователя в базе данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        telegram_id: ID пользователя в Telegram
        full_name: Полное имя пользователя

    Returns:
        Созданный объект Person
    """
    person = Person(
        telegram_id=telegram_id,
        full_name=full_name,
    )
    session.add(person)
    await session.flush()
    await session.refresh(person)
    return person
