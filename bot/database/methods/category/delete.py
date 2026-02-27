from sqlalchemy.ext.asyncio import AsyncSession

from database.models.category import Category


async def delete_category(
    session: AsyncSession,
    category: Category,
) -> None:
    """
    Удаляет категорию из базы данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        category: Объект Category для удаления
    """
    session.delete(category)
    await session.flush()

