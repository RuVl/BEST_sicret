from sqlalchemy.ext.asyncio import AsyncSession

from database.models import Person


async def set_lbg_member(session: AsyncSession, person: Person, lbg_member_id: int) -> None:
    """Привязать Person к участнику LBG. Коммит - на вызывающей стороне."""
    person.lbg_member_id = lbg_member_id
