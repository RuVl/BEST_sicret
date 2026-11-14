from best_db.models import Category
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_categories(session: AsyncSession) -> list[Category]:
    query = select(Category)
    result = await session.execute(query)
    categories = result.scalars().all()
    return list(categories)
