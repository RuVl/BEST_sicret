from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from database.models import VpnSubscription


async def mark_revoked(session: AsyncSession, subscription: VpnSubscription) -> None:
    """Пометить подписку отозванной. Коммит — на вызывающей стороне."""
    subscription.status = "revoked"
    subscription.revoked_at = datetime.now(UTC)


async def mark_active(session: AsyncSession, subscription: VpnSubscription) -> None:
    """Вернуть подписку в строй после автовосстановления."""
    subscription.status = "active"
    subscription.revoked_at = None


async def set_client_identity(
    session: AsyncSession,
    subscription: VpnSubscription,
    *,
    xui_email: str,
    sub_id: str,
    xui_client_uuid: str,
) -> None:
    """Переписать идентификаторы клиента после перевыпуска (на ``person_id`` уникальный индекс)."""
    subscription.xui_email = xui_email
    subscription.sub_id = sub_id
    subscription.xui_client_uuid = xui_client_uuid
    subscription.status = "active"
    subscription.revoked_at = None
    subscription.issued_at = datetime.now(UTC)
