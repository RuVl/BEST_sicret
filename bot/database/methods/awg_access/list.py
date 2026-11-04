from best_db.models import AwgAccess, LbgMember, Person
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.methods.member.predicates import left_lbg


async def list_accesses_to_suspend(session: AsyncSession) -> list[AwgAccess]:
    """Действующие разрешения людей, которые больше не состоят в LBG.

    Условие то же, что у ``list_subscriptions_to_revoke``: привязку сняли, участника
    исключили или он пропал из таблицы. ``Person`` нужен джобу для уведомления.
    """
    query = (
        select(AwgAccess)
        .join(Person, AwgAccess.person_id == Person.id)
        .outerjoin(LbgMember, Person.lbg_member_id == LbgMember.id)
        .where(AwgAccess.status == "granted")
        .where(left_lbg())
        .options(joinedload(AwgAccess.person))
    )
    return list(await session.scalars(query))
