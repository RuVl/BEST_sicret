from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.category import Category


async def get_category_by_id(
    session: AsyncSession,
    category_id: int,
) -> Optional[Category]:
    """
    Получает категорию по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        category_id: ID категории

    Returns:
        Объект Category или None, если не найден
    """
    stmt = select(Category).where(Category.id == category_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_category_by_name(
    session: AsyncSession,
    name: str,
) -> Optional[Category]:
    """
    Получает категорию по названию.

    Args:
        session: Асинхронная сессия SQLAlchemy
        name: Название категории

    Returns:
        Объект Category или None, если не найден
    """
    stmt = select(Category).where(Category.name == name)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_all_categories(
    session: AsyncSession,
) -> List[Category]:
    """
    Получает все категории.

    Args:
        session: Асинхронная сессия SQLAlchemy

    Returns:
        Список всех категорий
    """
    stmt = select(Category).order_by(Category.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())

