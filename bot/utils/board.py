"""Привилегированные Telegram-ID, выведенные из текущего Board.

Приоритет — носитель роли в синхронизированных данных (LbgMember board + status_field),
связанный с ботом Person. Если такого нет (роль не опознана / человек не заходил в бота),
откатываемся на статический ID из env.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from database.methods.member import resolve_board_role
from env import settings


async def get_president_id(session: AsyncSession) -> int:
    person = await resolve_board_role(session, "president")
    return person.telegram_id if person else settings.telegram.PRESIDENT_ID


async def get_treasurer_id(session: AsyncSession) -> int:
    person = await resolve_board_role(session, "treasurer")
    return person.telegram_id if person else settings.telegram.TREASURER_ID
