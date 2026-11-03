from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.models import Person

from .set import claim_username


async def get_or_create_person(
    session: AsyncSession,
    telegram_id: int,
    full_name: str,
    username: str | None = None,
) -> Person:
    """Найти Person по ``telegram_id`` или создать нового.

    Имя и username обновляются на каждом заходе - в Telegram они могут меняться (и ник - исчезнуть).
    Коммит остаётся на вызывающей стороне.
    """
    person = await session.scalar(select(Person).where(Person.telegram_id == telegram_id))

    if person is None:
        person = Person(telegram_id=telegram_id, full_name=full_name)
        session.add(person)
        # id нужен claim_username, чтобы не снять ник с самого себя.
        await session.flush()
    else:
        person.full_name = full_name

    await claim_username(session, person, username)
    return person


async def get_person_with_member(session: AsyncSession, telegram_id: int) -> Person | None:
    """Person вместе со связанным LbgMember одним запросом.

    Нужен там, где решение зависит от членства (например, доступ к VPN): ``joinedload``
    избавляет от ленивой подгрузки после закрытия сессии.
    """
    query = select(Person).where(Person.telegram_id == telegram_id).options(joinedload(Person.lbg_member))
    return await session.scalar(query)


async def find_person_by_handle(session: AsyncSession, handle: int | str) -> Person | None:
    """Person по Telegram ID (``int``) или нику (``str`` без ``@``, см. ``parse_person_handle``), с членством.

    Ник уникален без учёта регистра (индекс в БД), поэтому человек находится не больше чем один.
    """
    query = select(Person).options(joinedload(Person.lbg_member))
    if isinstance(handle, int):
        query = query.where(Person.telegram_id == handle)
    else:
        query = query.where(func.lower(Person.telegram_username) == handle.lower())
    return await session.scalar(query)
