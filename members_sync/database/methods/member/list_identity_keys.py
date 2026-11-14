from best_db.models import LbgMember
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_identity_keys(session: AsyncSession) -> set[str]:
    """Все ключи в базе, вместе с пропавшими: вернувшийся оживает по своему ключу, он не новый."""
    return set(await session.scalars(select(LbgMember.identity_key)))
