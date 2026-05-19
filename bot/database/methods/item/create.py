from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Item


async def create_item(
    session: AsyncSession,
    name: str,
    category_id: int,
    count: int,
    unit: str,
    place_id: int,
) -> Item:
    item = Item(
        name=name,
        category_id=category_id,
        count=count,
        unit=unit,
        place_id=place_id,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item