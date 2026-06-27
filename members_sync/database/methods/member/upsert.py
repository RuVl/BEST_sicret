from datetime import datetime
from typing import TYPE_CHECKING, Literal

from best_db.models import LbgMember
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from parsing.member_builder import ParsedMember


async def upsert_member(
    session: AsyncSession,
    parsed: "ParsedMember",
    now: datetime,
) -> Literal["inserted", "updated"]:
    """Вставить или обновить участника по ``identity_key``.

    ``first_seen_at``/``created_at`` сохраняются при обновлении. Сбрасывает
    ``removed_from_sheet_at`` — раз участник встретился, он снова «в таблице».
    """
    values = parsed.to_db_values()

    existing = await session.scalar(select(LbgMember).where(LbgMember.identity_key == parsed.identity_key))

    if existing is None:
        member = LbgMember(**values)
        member.first_seen_at = now
        member.last_seen_at = now
        member.last_synced_at = now
        member.removed_from_sheet_at = None
        session.add(member)
        return "inserted"

    for key, value in values.items():
        setattr(existing, key, value)
    existing.last_seen_at = now
    existing.last_synced_at = now
    existing.removed_from_sheet_at = None
    return "updated"
