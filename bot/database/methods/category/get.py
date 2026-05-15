from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Category


async def get_categories(session: AsyncSession) -> list[Category]:
    query = select(Category)
    result = await session.execute(query)
    categories = result.scalars().all()
    return list(categories)
