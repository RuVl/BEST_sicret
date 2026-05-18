from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models.category import Category


async def get_categories(session: AsyncSession) -> list[Category]:
    query = select(Category)
    result = await session.execute(query)
    categories = result.scalars().all()
    return categories

async def get_category_by_id(session: AsyncSession, category_id: int) -> Category | None:
    query = select(Category).where(Category.id == category_id)
    result = await session.execute(query)
    return result.scalar_one_or_none()
