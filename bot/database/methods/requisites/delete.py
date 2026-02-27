from sqlalchemy.ext.asyncio import AsyncSession

from database.models.requisites import Requisites


async def delete_requisites(
    session: AsyncSession,
    requisites: Requisites,
) -> None:
    """
    Удаляет реквизиты из базы данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        requisites: Объект Requisites для удаления
    """
    session.delete(requisites)
    await session.flush()
