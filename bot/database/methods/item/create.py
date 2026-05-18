from sqlalchemy.ext.asyncio import AsyncSession
from database.models import Item


async def create_item(
    session: AsyncSession,
    name: str,
    category_id: int,
    count: int,
    unit: str,
    description: str = ""
) -> Item:
    item = Item(
        name=name,
        category_id=category_id,
        count=count,
        unit=unit,
        description=description if description else ""
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item