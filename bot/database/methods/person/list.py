from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import LbgMember, Person


async def list_member_persons(session: AsyncSession) -> list[Person]:
    """Все, кто нажимал /start и привязан к мемберу LBG, вместе с членством.

    Состоит ли человек в LBG сейчас, решает ``current_member`` - условие держим в одном месте.
    """
    query = (
        select(Person)
        .join(LbgMember, Person.lbg_member_id == LbgMember.id)
        .options(joinedload(Person.lbg_member))
        .order_by(Person.id)
    )
    return list(await session.scalars(query))
