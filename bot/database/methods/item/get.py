from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database.models import Item


async def get_items_by_categories_id(
    session: AsyncSession, category_id: int
) -> list[Item]:
    query = select(Item).where(Item.category_id == category_id)
    result = await session.execute(query)
    items = result.scalars().all()
    return list(items)


async def get_items_by_category(session: AsyncSession, category_id: int) -> list[Item]:
    query = (
        select(Item)
        .where(Item.category_id == category_id)
        .options(selectinload(Item.place))
    )
    result = await session.execute(query)
    category_items_with_place = result.scalars().all()
    return list(category_items_with_place)


async def get_item_by_id(session: AsyncSession, item_id: int) -> Item | None:
    query = select(Item).where(Item.id == item_id).options(selectinload(Item.place))
    result = await session.execute(query)
    return result.scalar_one_or_none()
