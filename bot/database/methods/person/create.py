from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from database.models.person import Person


async def create_person(
        session: AsyncSession,
        telegram_id: int,
        full_name: str,
) -> Person:
    """
    Создает нового пользователя в базе данных.

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
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise
    return person
