from sqlalchemy.ext.asyncio import AsyncSession

from database.models.category import Category


async def delete_category(
    session: AsyncSession,
    category: Category,
) -> None:
    """
    Удаляет категорию из базы данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        category: Объект Category для удаления
    """
    await session.delete(category)
    await session.flush()

