from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Person


async def get_or_create_person(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: str | None = None,
) -> Person:
    """Найти Person по ``telegram_id`` или создать нового.

    Имя и username обновляются на каждом заходе — в Telegram они могут меняться.
    Коммит остаётся на вызывающей стороне.
    """
    person = await session.scalar(select(Person).where(Person.telegram_id == telegram_id))

    if person is None:
        person = Person(telegram_id=telegram_id, full_name=full_name, telegram_username=username)
        session.add(person)
        await session.flush()
        return person

    person.full_name = full_name
    if username is not None:
        person.telegram_username = username
    return person


async def get_person_with_member(session: AsyncSession, telegram_id: int) -> Person | None:
    """Person вместе со связанным LbgMember одним запросом.

    Нужен там, где решение зависит от членства (например, доступ к VPN): ``joinedload``
    избавляет от ленивой подгрузки после закрытия сессии.
    """
    query = select(Person).where(Person.telegram_id == telegram_id).options(joinedload(Person.lbg_member))
    return await session.scalar(query)
