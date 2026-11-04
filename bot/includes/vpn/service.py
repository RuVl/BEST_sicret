"""Доменные операции над VPN-подпиской: выпуск, перевыпуск, восстановление.

Порядок всегда один: сначала панель, потом БД бота. Если запись в БД не доехала, повторный
вход находит уже созданного клиента по email и досоздаёт строку, а не плодит второго клиента.

Панель - источник правды: клиента могли удалить или выключить в её админке, и бот обязан
починиться сам, а не показывать выдуманное состояние.
"""

from uuid import uuid4

import structlog
from best_db.models import LbgMember, Person, VpnSubscription
from py3xui import AsyncApi, Client, ClientDetails, ClientEntry
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from database.methods.vpn_subscription import (
    create_subscription,
    get_subscription_by_email,
    get_subscription_by_person,
    mark_active,
    set_client_identity,
)
from env import settings
from includes.vpn.identity import belongs_to_person, build_client_email, fallback_client_email
from includes.vpn.panel import raise_for_skipped, set_clients_enabled

logger: FilteringBoundLogger = structlog.get_logger("vpn")

# XTLS-Vision - единственный flow, который мы выдаём: панель на update перезаписывает поле
# тем, что пришло в теле, поэтому пустой flow молча снёс бы настройку клиента.
DEFAULT_FLOW = "xtls-rprx-vision"


def subscription_url(sub_id: str) -> str:
    """Ссылка-подписка человека. Внешний адрес панель не знает, он задан в настройках бота."""
    return f"{settings.xui.SUB_BASE_URL.rstrip('/')}/{sub_id}"


def person_comment(person: Person, member: LbgMember | None) -> str:
    """Подпись клиента в панели - ФИО, как в таблице мемберов (общая для VLESS и AmneziaWG)."""
    return (member.full_name_ru if member else None) or person.full_name


def _person_names(person: Person, member: LbgMember) -> tuple[str, ...]:
    """ФИО, под которыми человек может быть записан в панели."""
    return tuple(name for name in (member.full_name_ru, person.full_name) if name)


async def _resolve_target(
    session: AsyncSession,
    api: AsyncApi,
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

    details = await api.client.get_details(email)
    if details is None or email == fallback:
        # На fallback-идентификаторе клиент может остаться от попытки, у которой не доехал коммит.
        return email, details

    known = await get_subscription_by_email(session, email)
    if known is not None:
        ours = known.person_id == person.id
    else:
        ours = belongs_to_person(
            # У библиотеки поле шире, чем у панели (int | str | None): незаполненное - это 0.
            client_tg_id=int(details.client.tg_id or 0),
            client_comment=details.client.comment,
            telegram_id=person.telegram_id,
            full_names=_person_names(person, member),
        )
    if ours:
        return email, details

    await logger.awarning("vpn-email-taken", person_id=person.id, email=email)
    return fallback, await api.client.get_details(fallback)


def _build_client(person: Person, member: LbgMember, email: str) -> Client:
    """Новый клиент панели: безлимит трафика и срока, ограничение по IP, месячный сброс счётчика."""
    return Client(
        id=str(uuid4()),
        email=email,
        sub_id=uuid4().hex,
        enable=True,
        flow=DEFAULT_FLOW,
        tg_id=person.telegram_id,
        comment=person_comment(person, member),
        group=settings.xui.GROUP,
        limit_ip=settings.xui.CLIENT_IP_LIMIT,
        reset=settings.xui.TRAFFIC_RESET_DAYS,
    )


async def _adopt_client(api: AsyncApi, details: ClientDetails, person: Person, member: LbgMember) -> None:
    """Взять существующего клиента панели под управление бота.

    Лимиты и прочее, выставленное руками, не трогаем - дописываем только принадлежность
    (tg-id, ФИО, группу), выставляем свой flow и включаем клиента, если он был выключен.
    Панель заменяет клиента телом запроса, поэтому правим прочитанного, а не собираем нового.
    """
    client = details.client
    client.enable = True
    client.flow = DEFAULT_FLOW
    client.tg_id = person.telegram_id
    client.comment = person_comment(person, member)
    client.group = settings.xui.GROUP
    await api.client.update(client.uuid or "", client)


async def _acquire_client(
    session: AsyncSession,
    api: AsyncApi,
    person: Person,
    member: LbgMember,
) -> tuple[str, str, str]:
    """Получить готового клиента панели: ``(email, sub_id, uuid)``.

    Сначала панель, потом БД бота: если запись в БД не доедет, следующий заход подберёт
    того же клиента, а не создаст второго.
    """
    email, details = await _resolve_target(session, api, person, member)

    if details is not None:
        await _adopt_client(api, details, person, member)
        await logger.ainfo("vpn-client-adopted", person_id=person.id, email=email)
        return email, details.client.sub_id, details.client.uuid or ""

    client = _build_client(person, member, email)
    # add() py3xui заводит клиента только в одном инбаунде, а bulk_add - сразу во всех одним запросом:
    # неверный инбаунд не оставит клиента привязанным к части из них.
    raise_for_skipped(await api.client.bulk_add([ClientEntry(client=client, inbound_ids=settings.xui.INBOUND_IDS)]))
    await logger.ainfo("vpn-client-created", person_id=person.id, email=email, inbound_ids=settings.xui.INBOUND_IDS)
    return client.email, client.sub_id, str(client.id)


async def ensure_subscription(
    session: AsyncSession,
    api: AsyncApi,
    person: Person,
    member: LbgMember,
) -> VpnSubscription:
    """Привести подписку человека в рабочее состояние. Коммит - на вызывающей стороне.

    Разбирает все расхождения между БД бота и панелью: подписки нет, клиента удалили руками,
    подписку отозвал джоб, клиент просто выключен.
    """
    subscription = await get_subscription_by_person(session, person.id)

    if subscription is None:
        return await issue_subscription(session, api, person, member)

    details = await api.client.get_details(subscription.xui_email)

    if details is None:
        # Клиента снесли в админке - выпускаем нового и переписываем идентификаторы в той же строке.
        return await reissue_subscription(session, api, person, member, subscription)

    if not details.client.enable or subscription.status != "active":
        await restore_subscription(session, api, subscription)

    return subscription


async def issue_subscription(
    session: AsyncSession,
    api: AsyncApi,
    person: Person,
    member: LbgMember,
) -> VpnSubscription:
    """Первая выдача: завести клиента в панели (или подхватить готового) и записать в БД."""
    email, sub_id, uuid = await _acquire_client(session, api, person, member)

    return await create_subscription(
        session,
        person_id=person.id,
        xui_email=email,
        sub_id=sub_id,
        xui_client_uuid=uuid,
    )


async def reissue_subscription(
    session: AsyncSession,
    api: AsyncApi,
    person: Person,
    member: LbgMember,
    subscription: VpnSubscription,
) -> VpnSubscription:
    """Клиента удалили в панели: заводим нового и обновляем существующую строку.

    Новая строка не подойдёт - на ``person_id`` стоит уникальный индекс. Ссылка у человека
    меняется: старый ``subId`` вместе с клиентом уже уничтожен.
    """
    email, sub_id, uuid = await _acquire_client(session, api, person, member)

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
    api: AsyncApi,
    subscription: VpnSubscription,
) -> None:
    """Мембер вернулся: включаем прежнего клиента, ссылка остаётся той же."""
    await set_clients_enabled(api, [subscription.xui_email], True)
    await mark_active(session, subscription)
    await logger.ainfo("vpn-subscription-restored", person_id=subscription.person_id)
