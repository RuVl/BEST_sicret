from sqlalchemy.ext.asyncio import AsyncSession

from database.models.person import Person


async def delete_person(
    session: AsyncSession,
    person: Person,
) -> None:
    """
    Удаляет пользователя из базы данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        person: Объект Person для удаления
    """
    await session.delete(person)
    await session.flush()

