from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from database.models import Category


async def get_all_categories(session: AsyncSession) -> list[Category]:
    result = await session.execute(select(Category))
    return result.scalars().all()