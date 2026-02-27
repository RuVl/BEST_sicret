from sqlalchemy.ext.asyncio import AsyncSession

from database.models.person import Person


async def delete_person(
    session: AsyncSession,
    person: Person,
) -> None:
    """
    Удаляет пользователя из базы данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        person: Объект Person для удаления
    """
    session.delete(person)
    await session.flush()

