from best_db.matching import normalize_telegram_handle
from best_db.models import LbgMember, Person
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def link_unlinked_persons(session: AsyncSession) -> int:
    """Дотянуть связь Person → LbgMember по Telegram-username, вернуть число связанных.

    Бот при ``/start`` сохраняет ``Person.telegram_username`` и связывает сразу, если
    участник уже в таблице. Здесь — обратный случай: человек написал боту раньше, чем
    появился/обновился в Google Sheets. Коммит — на вызывающей стороне.
    """
    persons = (
        await session.scalars(
            select(Person).where(Person.lbg_member_id.is_(None)).where(Person.telegram_username.is_not(None))
        )
    ).all()
    if not persons:
        return 0

    # Нормализованный username → id ещё не связанного участника.
    members = (
        await session.scalars(select(LbgMember).where(LbgMember.telegram.is_not(None)).where(~LbgMember.person.has()))
    ).all()
    by_handle: dict[str, int] = {}
    for member in members:
        handle = normalize_telegram_handle(member.telegram)
        if handle and handle not in by_handle:
            by_handle[handle] = member.id

    linked = 0
    for person in persons:
        handle = normalize_telegram_handle(person.telegram_username)
        member_id = by_handle.pop(handle, None) if handle else None
        if member_id is not None:
            person.lbg_member_id = member_id
            linked += 1
    return linked
