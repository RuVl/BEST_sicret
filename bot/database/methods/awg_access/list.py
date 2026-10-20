from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import AwgAccess, LbgMember, Person


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
        .where(
            or_(
                Person.lbg_member_id.is_(None),
                LbgMember.is_excluded.is_(True),
                LbgMember.removed_from_sheet_at.is_not(None),
            )
        )
        .options(joinedload(AwgAccess.person))
    )
    return list(await session.scalars(query))
