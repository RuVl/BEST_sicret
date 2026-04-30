from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.category import Category


async def get_categories(session: AsyncSession) -> list[Category]:
    query = select(Category)
    result = await session.execute(query)
    categories = result.scalars().all()
    return categories

