from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.category import Category


async def update_category(
    session: AsyncSession,
    category: Category,
    name: Optional[str] = None,
) -> Category:
    """
    Обновляет данные категории.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        category: Объект Category для обновления
        name: Новое название категории (опционально)

    Returns:
        Обновленный объект Category
    """
    if name is not None:
        category.name = name
    
    await session.flush()
    await session.refresh(category)
    return category

