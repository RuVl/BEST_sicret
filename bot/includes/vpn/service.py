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
from includes.vpn.identity import belongs_to_person, build_client_email, fallback_client_email
from includes.vpn.schemas import DEFAULT_FLOW, ClientDetails, XuiClientPayload

logger: FilteringBoundLogger = structlog.get_logger("vpn")


def person_comment(person: Person, member: LbgMember | None) -> str:
    """Подпись клиента в панели - ФИО, как в таблице мемберов (общая для VLESS и AmneziaWG)."""
    return (member.full_name_ru if member else None) or person.full_name


def _person_names(person: Person, member: LbgMember) -> tuple[str, ...]:
    """ФИО, под которыми человек может быть записан в панели."""
    return tuple(name for name in (member.full_name_ru, person.full_name) if name)


async def _resolve_target(
    session: AsyncSession,
    client: XuiClient,
    person: Person,
    member: LbgMember,
) -> tuple[str, ClientDetails | None]:
    """Выбрать идентификатор клиента и подобрать уже существующего клиента панели.

    Возвращаем ``(email, details)``: ``details`` - клиент, которого можно взять себе, а не
    создавать заново. Своим считаем клиента из подписки этого же человека и заведённого руками,
    у которого сходятся почта, tg-id и ФИО. Чужого не трогаем и уходим на ``lbg-<person_id>``:
    в том числе подписку другого ``Person`` с той же почтой (сменил Telegram-аккаунт, дубль
    почты в таблице) - иначе бот переписал бы чужого клиента и упёрся в уникальность строки.
    """
    email = build_client_email(person.id, member.best_email)
    fallback = fallback_client_email(person.id)

    details = await client.get_client_details(email)
    if details is None or email == fallback:
        # На fallback-идентификаторе клиент может остаться от попытки, у которой не доехал коммит.
        return email, details

    known = await get_subscription_by_email(session, email)
    if known is not None:
        ours = known.person_id == person.id
    else:
        record = details.record
        ours = belongs_to_person(
            client_tg_id=record.tg_id,
            client_comment=record.comment,
            telegram_id=person.telegram_id,
            full_names=_person_names(person, member),
        )
    if ours:
        return email, details

    await logger.awarning("vpn-email-taken", person_id=person.id, email=email)
    return fallback, await client.get_client_details(fallback)


def _build_payload(person: Person, member: LbgMember, email: str) -> XuiClientPayload:
    """Новый клиент панели: безлимит трафика и срока, ограничение по IP, месячный сброс счётчика."""
    return XuiClientPayload(
        id=str(uuid4()),
        email=email,
        subId=uuid4().hex,
        enable=True,
        tgId=person.telegram_id,
        comment=person_comment(person, member),
        group=settings.xui.GROUP,
        limitIp=settings.xui.CLIENT_IP_LIMIT,
        totalGB=0,
        expiryTime=0,
        reset=settings.xui.TRAFFIC_RESET_DAYS,
    )


async def _adopt_client(client: XuiClient, details: ClientDetails, person: Person, member: LbgMember) -> None:
    """Взять существующего клиента панели под управление бота.

    Лимиты и прочее, выставленное руками, не трогаем - дописываем только принадлежность
    (tg-id, ФИО, группу), выставляем свой flow и включаем клиента, если он был выключен.
    """
    body = details.update_body(
        enable=True,
        flow=DEFAULT_FLOW,
        tgId=person.telegram_id,
        comment=person_comment(person, member),
        group=settings.xui.GROUP,
    )
    await client.update_client(details.record.email, body)


async def _acquire_client(
    session: AsyncSession,
    client: XuiClient,
    person: Person,
    member: LbgMember,
) -> tuple[str, str, str]:
    """Получить готового клиента панели: ``(email, sub_id, uuid)``.

    Сначала панель, потом БД бота: если запись в БД не доедет, следующий заход подберёт
    того же клиента, а не создаст второго.
    """
    email, details = await _resolve_target(session, client, person, member)

    if details is not None:
        await _adopt_client(client, details, person, member)
        await logger.ainfo("vpn-client-adopted", person_id=person.id, email=email)
        record = details.record
        return email, record.sub_id, record.uuid

    payload = _build_payload(person, member, email)
    await client.add_client(payload, settings.xui.INBOUND_IDS)
    return payload.email, payload.sub_id, payload.id


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
    """Первая выдача: завести клиента в панели (или подхватить готового) и записать в БД."""
    email, sub_id, uuid = await _acquire_client(session, client, person, member)

    return await create_subscription(
        session,
        person_id=person.id,
        xui_email=email,
        sub_id=sub_id,
        xui_client_uuid=uuid,
    )


async def reissue_subscription(
    session: AsyncSession,
    client: XuiClient,
    person: Person,
    member: LbgMember,
    subscription: VpnSubscription,
) -> VpnSubscription:
    """Клиента удалили в панели: заводим нового и обновляем существующую строку.

    Новая строка не подойдёт - на ``person_id`` стоит уникальный индекс. Ссылка у человека
    меняется: старый ``subId`` вместе с клиентом уже уничтожен.
    """
    email, sub_id, uuid = await _acquire_client(session, client, person, member)

    await set_client_identity(
        session,
        subscription,
        xui_email=email,
        sub_id=sub_id,
        xui_client_uuid=uuid,
    )
    await logger.awarning("vpn-subscription-reissued", person_id=person.id, email=email)
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
