from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.models import Item


async def get_items_by_category(session: AsyncSession, category_id: int) -> list[Item]:
    result = await session.execute(
        select(Item)
        .where(Item.category_id == category_id)
        .options(selectinload(Item.place))
    )
    return result.scalars().all()


async def get_item_by_id(session: AsyncSession, item_id: int) -> Item | None:
    result = await session.execute(
        select(Item)
        .where(Item.id == item_id)
        .options(selectinload(Item.place))
    )
    return result.scalar_one_or_none()