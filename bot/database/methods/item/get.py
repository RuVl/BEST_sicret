from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Item


async def get_items_by_categories_id(session: AsyncSession, category_id: int) -> list[Item]:
    query = select(Item).where(Item.category_id == category_id)
    result = await session.execute(query)
    items = result.scalars().all()
    return items