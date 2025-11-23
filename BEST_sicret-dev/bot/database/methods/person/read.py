from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.person import Person


async def get_person_by_id(
    session: AsyncSession,
    person_id: int,
) -> Optional[Person]:
    """
    Получает пользователя по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        person_id: ID пользователя

    Returns:
        Объект Person или None, если не найден
    """
    stmt = select(Person).where(Person.id == person_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_person_by_telegram_id(
    session: AsyncSession,
    telegram_id: int,
) -> Optional[Person]:
    """
    Получает пользователя по Telegram ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        telegram_id: ID пользователя в Telegram

    Returns:
        Объект Person или None, если не найден
    """
    stmt = select(Person).where(Person.telegram_id == telegram_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()

