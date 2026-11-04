from sqlalchemy import func, update
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Person


async def set_lbg_member(session: AsyncSession, person: Person, lbg_member_id: int) -> None:
    """Привязать Person к участнику LBG. Коммит - на вызывающей стороне."""
    person.lbg_member_id = lbg_member_id


async def release_lbg_members(session: AsyncSession, lbg_member_ids: list[int], username: str) -> None:
    """Снять этих участников со всех Person, кроме владельца ника: иначе /start его к ним не привяжет.

    ``username`` - в нижнем регистре. Коммит - на вызывающей стороне.
    """
    await session.execute(
        update(Person)
        .where(Person.lbg_member_id.in_(lbg_member_ids))
        .where(func.lower(Person.telegram_username).is_distinct_from(username))
        .values(lbg_member_id=None)
    )


async def claim_username(session: AsyncSession, person: Person, username: str | None) -> None:
    """Закрепить ник Telegram за человеком; ``None`` - человек убрал ник, забываем и мы.

    Telegram отдаёт ник одному человеку за раз, так что у другого Person в БД он устарел: тот сменил
    ник и с тех пор не нажимал /start. Снимаем его в той же транзакции - иначе упрёмся в уникальный
    индекс, а по чужому нику CLI нашёл бы, а ``members_sync`` связал бы не того человека.
    Коммит - на вызывающей стороне.
    """
    current = person.telegram_username
    if username is not None and (current is None or current.lower() != username.lower()):
        await session.execute(
            update(Person)
            .where(func.lower(Person.telegram_username) == username.lower())
            .where(Person.id != person.id)
            .values(telegram_username=None)
        )
    person.telegram_username = username
