from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AwgAccess


async def mark_granted(session: AsyncSession, access: AwgAccess) -> None:
    """Доступ снова в силе: админ выдал повторно или мембер вернулся. Коммит - на вызывающей стороне."""
    if access.status == "revoked":
        access.granted_at = datetime.now(UTC)
    access.status = "granted"
    access.disabled_at = None


async def mark_suspended(session: AsyncSession, access: AwgAccess) -> None:
    """Человек выбыл из LBG: ключ выключен, но вернётся сам вместе с членством."""
    access.status = "suspended"
    access.disabled_at = datetime.now(UTC)


async def mark_revoked(session: AsyncSession, access: AwgAccess) -> None:
    """Админ забрал доступ: кнопка пропадает, ключ выключен до повторной выдачи."""
    access.status = "revoked"
    access.disabled_at = datetime.now(UTC)


async def mark_issued(session: AsyncSession, access: AwgAccess) -> None:
    """Конфиг отправлен человеку."""
    access.issued_at = datetime.now(UTC)
