import re

from best_db.matching import normalize_telegram_handle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import LbgMember, Person

# Ключевые слова ролей в свободном тексте LbgMember.status_field (рус./англ.).
_ROLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "president": re.compile(r"president|президент", re.IGNORECASE),
    "treasurer": re.compile(r"treasurer|казначей", re.IGNORECASE),
    "hr": re.compile(r"vp4hr", re.IGNORECASE),
}


async def find_member_by_username(session: AsyncSession, username: str | None) -> LbgMember | None:
    """Найти ещё не связанного участника по Telegram-username.

    ``telegram`` в таблице хранится «как есть» (грязный хэндл), поэтому сравниваем по
    нормализованному виду в Python: грузим только несвязанных с непустым ``telegram``.
    """
    target = normalize_telegram_handle(username)
    if target is None:
        return None

    query = select(LbgMember).where(LbgMember.telegram.is_not(None)).where(~LbgMember.person.has())
    for member in await session.scalars(query):
        if normalize_telegram_handle(member.telegram) == target:
            return member
    return None


async def resolve_board_role(session: AsyncSession, role: str) -> Person | None:
    """Найти Person текущего носителя board-роли (president/treasurer/hr).

    «Текущий» = состоит в board-листе (``membership_category == 'board'``) и его роль
    угадывается по ``status_field``. Возвращает только уже связанного с ботом Person
    (у несвязанного нет ``telegram_id`` для уведомлений).
    """
    pattern = _ROLE_PATTERNS.get(role)
    if pattern is None:
        return None

    query = (
        select(Person, LbgMember.status_field)
        .join(LbgMember, Person.lbg_member_id == LbgMember.id)
        .where(LbgMember.membership_category == "board")
        .where(LbgMember.status_field.is_not(None))
    )
    for person, status_field in await session.execute(query):
        if pattern.search(status_field or ""):
            return person
    return None
