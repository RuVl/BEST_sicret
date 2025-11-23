from typing import Optional, List

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models.item import Item


async def get_item_by_id(
    session: AsyncSession,
    item_id: int,
) -> Optional[Item]:
    """
    Получает товар по ID.

    Args:
        session: Асинхронная сессия SQLAlchemy
        item_id: ID товара

    Returns:
        Объект Item или None, если не найден
    """
    stmt = select(Item).where(Item.id == item_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_items_by_category_id(
    session: AsyncSession,
    category_id: int,
) -> List[Item]:
    """
    Получает все предметы по ID категории.

    Args:
        session: Асинхронная сессия SQLAlchemy
        category_id: ID категории

    Returns:
        Список предметов категории
    """
    stmt = select(Item).where(Item.category_id == category_id).order_by(Item.name)
    result = await session.execute(stmt)
    return list(result.scalars().all())





