from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import LbgMember, Person, VpnSubscription


async def list_subscriptions_to_revoke(session: AsyncSession) -> list[VpnSubscription]:
    """Активные подписки людей, которые больше не активные мемберы LBG.

    Ловим два случая: привязку к участнику сняли совсем и участник перестал быть активным.
    ``Person`` подгружается сразу — джобу нужен ``telegram_id`` для уведомления.
    """
    query = (
        select(VpnSubscription)
        .join(Person, VpnSubscription.person_id == Person.id)
        .outerjoin(LbgMember, Person.lbg_member_id == LbgMember.id)
        .where(VpnSubscription.status == "active")
        .where(or_(Person.lbg_member_id.is_(None), LbgMember.is_active.is_(False)))
        .options(joinedload(VpnSubscription.person))
    )
    return list(await session.scalars(query))
