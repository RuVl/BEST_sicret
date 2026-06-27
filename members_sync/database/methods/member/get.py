from best_db.models import LbgMember
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def get_member_by_identity(session: AsyncSession, identity_key: str) -> LbgMember | None:
    return await session.scalar(select(LbgMember).where(LbgMember.identity_key == identity_key))


async def count_members(session: AsyncSession) -> int:
    return await session.scalar(select(func.count()).select_from(LbgMember)) or 0
