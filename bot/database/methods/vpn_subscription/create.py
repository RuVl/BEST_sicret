from sqlalchemy.ext.asyncio import AsyncSession

from database.models import VpnSubscription


async def create_subscription(
    session: AsyncSession,
    *,
    person_id: int,
    xui_email: str,
    sub_id: str,
    xui_client_uuid: str,
) -> VpnSubscription:
    """Создать запись о выданной подписке. Коммит — на вызывающей стороне."""
    subscription = VpnSubscription(
        person_id=person_id,
        xui_email=xui_email,
        sub_id=sub_id,
        xui_client_uuid=xui_client_uuid,
        status="active",
    )
    session.add(subscription)
    await session.flush()
    return subscription
