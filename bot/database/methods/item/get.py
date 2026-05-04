from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Item


async def get_items_by_category_id(
    session: AsyncSession,
    category_id: int,
) -> list[Item]:
    query = select(Item).where(Item.category_id == category_id)
    result = await session.execute(query)
    items = result.scalars().all()
    return list(items)


async def get_item(session: AsyncSession, item_id: int) -> Item | None:
    query = select(Item).where(Item.id == item_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()
