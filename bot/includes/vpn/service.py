"""Доменные операции над VPN-подпиской: выпуск, перевыпуск, восстановление.

Порядок всегда один: сначала панель, потом БД бота. Если запись в БД не доехала, повторный
вход находит уже созданного клиента по email и досоздаёт строку, а не плодит второго клиента.

Панель - источник правды: клиента могли удалить или выключить в её админке, и бот обязан
починиться сам, а не показывать выдуманное состояние.
"""

from uuid import uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from database.methods.vpn_subscription import (
    create_subscription,
    get_subscription_by_email,
    get_subscription_by_person,
    mark_active,
    set_client_identity,
)
from database.models import LbgMember, Person, VpnSubscription
from env import settings
from includes.vpn.client import XuiClient
from includes.vpn.identity import build_client_email, fallback_client_email
from includes.vpn.schemas import XuiClientPayload

logger: FilteringBoundLogger = structlog.get_logger("vpn")


async def _resolve_email(session: AsyncSession, client: XuiClient, person: Person, best_email: str | None) -> str:
    """Выбрать свободный идентификатор клиента.

    Best-почта может оказаться занята клиентом, заведённым в панели руками, - такого клиента
    не трогаем и уходим на собственный ``lbg-<person_id>``.
    """
    email = build_client_email(person.id, best_email)
    fallback = fallback_client_email(person.id)

    if email == fallback:
        return fallback

    record = await client.get_client(email)
    if record is None:
        return email

    # Клиент есть: наш (запись в БД) - переиспользуем, чужой - берём собственный идентификатор.
    known = await get_subscription_by_email(session, email)
    return email if known is not None else fallback


def _build_payload(person: Person, member: LbgMember, email: str) -> XuiClientPayload:
    """Новый клиент панели: безлимит трафика и срока, ограничение по IP, месячный сброс счётчика."""
    return XuiClientPayload(
        id=str(uuid4()),
        email=email,
        subId=uuid4().hex,
        enable=True,
        tgId=person.telegram_id,
        comment=member.full_name_ru or person.full_name,
        group=settings.xui.GROUP,
        limitIp=settings.xui.CLIENT_IP_LIMIT,
        totalGB=0,
        expiryTime=0,
        reset=settings.xui.TRAFFIC_RESET_DAYS,
    )


async def ensure_subscription(
    session: AsyncSession,
    client: XuiClient,
    person: Person,
    member: LbgMember,
) -> VpnSubscription:
    """Привести подписку человека в рабочее состояние. Коммит - на вызывающей стороне.

    Разбирает все расхождения между БД бота и панелью: подписки нет, клиента удалили руками,
    подписку отозвал джоб, клиент просто выключен.
    """
    subscription = await get_subscription_by_person(session, person.id)

    if subscription is None:
        return await issue_subscription(session, client, person, member)

    record = await client.get_client(subscription.xui_email)

    if record is None:
        # Клиента снесли в админке - выпускаем нового и переписываем идентификаторы в той же строке.
        return await reissue_subscription(session, client, person, member, subscription)

    if not record.enable or subscription.status != "active":
        await restore_subscription(session, client, subscription)

    return subscription


async def issue_subscription(
    session: AsyncSession,
    client: XuiClient,
    person: Person,
    member: LbgMember,
) -> VpnSubscription:
    """Первая выдача: создать клиента в панели и запись в БД."""
    email = await _resolve_email(session, client, person, member.best_email)

    # Клиент мог остаться от прошлой попытки, у которой не доехал коммит.
    existing = await client.get_client(email)
    if existing is not None:
        await logger.awarning("vpn-adopt-orphan-client", person_id=person.id, email=email)
        return await create_subscription(
            session,
            person_id=person.id,
            xui_email=email,
            sub_id=existing.sub_id,
            xui_client_uuid=existing.uuid,
        )

    payload = _build_payload(person, member, email)
    await client.add_client(payload, settings.xui.INBOUND_IDS)

    return await create_subscription(
        session,
        person_id=person.id,
        xui_email=payload.email,
        sub_id=payload.sub_id,
        xui_client_uuid=payload.id,
    )


async def reissue_subscription(
    session: AsyncSession,
    client: XuiClient,
    person: Person,
    member: LbgMember,
    subscription: VpnSubscription,
) -> VpnSubscription:
    """Клиента удалили в панели: создаём нового и обновляем существующую строку.

    Новая строка не подойдёт - на ``person_id`` стоит уникальный индекс. Ссылка у человека
    меняется: старый ``subId`` вместе с клиентом уже уничтожен.
    """
    email = await _resolve_email(session, client, person, member.best_email)
    payload = _build_payload(person, member, email)
    await client.add_client(payload, settings.xui.INBOUND_IDS)

    await set_client_identity(
        session,
        subscription,
        xui_email=payload.email,
        sub_id=payload.sub_id,
        xui_client_uuid=payload.id,
    )
    await logger.awarning("vpn-subscription-reissued", person_id=person.id, email=payload.email)
    return subscription


async def restore_subscription(
    session: AsyncSession,
    client: XuiClient,
    subscription: VpnSubscription,
) -> None:
    """Мембер вернулся: включаем прежнего клиента, ссылка остаётся той же."""
    await client.set_enabled(subscription.xui_email, True)
    await mark_active(session, subscription)
    await logger.ainfo("vpn-subscription-restored", person_id=subscription.person_id)
