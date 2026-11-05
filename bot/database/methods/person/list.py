from best_db.models import AwgAccess, LbgMember, Person, VpnSubscription
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.methods.member.predicates import left_lbg


def _with_member(query):
    # Членство нужно вызывающему уже после закрытия сессии (ФИО в выводе CLI).
    return query.options(joinedload(Person.lbg_member)).order_by(Person.id)


async def list_all_persons(session: AsyncSession) -> list[Person]:
    """Все, кто хоть раз нажимал /start."""
    return list(await session.scalars(_with_member(select(Person))))


async def list_active_member_persons(session: AsyncSession) -> list[Person]:
    """Состоящие в LBG сейчас - SQL-двойник ``current_member`` (``left_lbg``)."""
    query = select(Person).outerjoin(LbgMember, Person.lbg_member_id == LbgMember.id).where(~left_lbg())
    return list(await session.scalars(_with_member(query)))


async def list_board_persons(session: AsyncSession) -> list[Person]:
    """Состоящие в LBG из board-листа - как при поиске носителя board-роли (``resolve_board_role``)."""
    query = (
        select(Person)
        .outerjoin(LbgMember, Person.lbg_member_id == LbgMember.id)
        .where(~left_lbg())
        .where(LbgMember.membership_category == "board")
    )
    return list(await session.scalars(_with_member(query)))


async def list_awg_persons(session: AsyncSession) -> list[Person]:
    """У кого есть доступ к AmneziaWG, кроме отозванного админом (приостановленным ключи вернутся)."""
    query = select(Person).join(AwgAccess, AwgAccess.person_id == Person.id).where(AwgAccess.status != "revoked")
    return list(await session.scalars(_with_member(query)))


async def list_vless_persons(session: AsyncSession) -> list[Person]:
    """У кого действующая VLESS-подписка."""
    query = (
        select(Person)
        .join(VpnSubscription, VpnSubscription.person_id == Person.id)
        .where(VpnSubscription.status == "active")
    )
    return list(await session.scalars(_with_member(query)))
