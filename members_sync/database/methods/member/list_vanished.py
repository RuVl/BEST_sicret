from collections.abc import Iterable

from best_db.models import LbgMember
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_vanished(session: AsyncSession, seen_identity_keys: Iterable[str]) -> list[LbgMember]:
    """Строки, которые считались присутствующими, но в этом прогоне не встретились."""
    seen = set(seen_identity_keys)
    rows = await session.scalars(select(LbgMember).where(LbgMember.removed_from_sheet_at.is_(None)))
    return [member for member in rows if member.identity_key not in seen]
