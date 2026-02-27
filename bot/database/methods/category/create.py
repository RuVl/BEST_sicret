from sqlalchemy.ext.asyncio import AsyncSession

from database.models.category import Category


async def create_category(
    session: AsyncSession,
    name: str,
) -> Category:
    """
    Создает новую категорию в базе данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        name: Название категории

    Returns:
        Созданный объект Category
    """
    category = Category(
        name=name,
    )
    session.add(category)
    await session.flush()
    await session.refresh(category)
    return category

