"""Группы получателей рассылки (``make broadcast group=…``): вычисляются из данных, без ручной разметки.

Новая группа = функция-запрос здесь и строка в ``AUDIENCES``. Каждая отдаёт людей вместе с членством:
CLI печатает по нему ФИО уже после закрытия сессии.
"""

from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import AwgAccess, Person, VpnSubscription
from utils.access import current_member

from .list import list_member_persons

type Audience = Callable[[AsyncSession], Awaitable[list[Person]]]


async def list_all_persons(session: AsyncSession) -> list[Person]:
    """Все, кто хоть раз нажимал /start."""
    query = select(Person).options(joinedload(Person.lbg_member)).order_by(Person.id)
    return list(await session.scalars(query))


async def list_active_members(session: AsyncSession) -> list[Person]:
    """Состоящие в LBG сейчас - по тому же предикату, что открывает им меню бота."""
    return [person for person in await list_member_persons(session) if current_member(person) is not None]


async def list_board_members(session: AsyncSession) -> list[Person]:
    """Активные мемберы из board-листа - как при поиске носителя board-роли (``resolve_board_role``)."""
    return [
        person
        for person in await list_active_members(session)
        if person.lbg_member is not None and person.lbg_member.membership_category == "board"
    ]


async def list_awg_persons(session: AsyncSession) -> list[Person]:
    """У кого есть доступ к AmneziaWG, кроме отозванного админом (приостановленные - тоже: ключи вернутся)."""
    query = (
        select(Person)
        .join(AwgAccess, AwgAccess.person_id == Person.id)
        .where(AwgAccess.status != "revoked")
        .options(joinedload(Person.lbg_member))
        .order_by(Person.id)
    )
    return list(await session.scalars(query))


async def list_vless_persons(session: AsyncSession) -> list[Person]:
    """У кого действующая VLESS-подписка."""
    query = (
        select(Person)
        .join(VpnSubscription, VpnSubscription.person_id == Person.id)
        .where(VpnSubscription.status == "active")
        .options(joinedload(Person.lbg_member))
        .order_by(Person.id)
    )
    return list(await session.scalars(query))


AUDIENCES: dict[str, Audience] = {
    "all": list_all_persons,
    "members": list_active_members,
    "board": list_board_members,
    "awg": list_awg_persons,
    "vless": list_vless_persons,
}
