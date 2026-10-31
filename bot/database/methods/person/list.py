from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import LbgMember, Person


async def list_active_member_persons(session: AsyncSession) -> list[Person]:
    """Все, кто нажимал /start и сейчас состоит в LBG - условие то же, что у ``current_member``."""
    query = (
        select(Person)
        .join(LbgMember, Person.lbg_member_id == LbgMember.id)
        .where(LbgMember.is_excluded.is_(False), LbgMember.removed_from_sheet_at.is_(None))
        .options(joinedload(Person.lbg_member))
        .order_by(Person.id)
    )
    return list(await session.scalars(query))
