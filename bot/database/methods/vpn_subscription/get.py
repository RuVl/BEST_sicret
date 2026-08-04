from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import VpnSubscription


async def get_subscription_by_person(session: AsyncSession, person_id: int) -> VpnSubscription | None:
    """Подписка человека (не более одной) или ``None``."""
    return await session.scalar(select(VpnSubscription).where(VpnSubscription.person_id == person_id))


async def get_subscription_by_email(session: AsyncSession, xui_email: str) -> VpnSubscription | None:
    """Подписка по идентификатору клиента в панели - для сверки с чужими (ручными) клиентами."""
    return await session.scalar(select(VpnSubscription).where(VpnSubscription.xui_email == xui_email))
