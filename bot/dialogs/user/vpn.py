"""Поддиалог VPN-подписки: статус, выпуск, ссылка и трафик.

Источник правды по состоянию ключа - панель 3x-ui; в БД бота лежат только идентификаторы.

Тем, кому админ выдал AmneziaWG (``make awg-grant``), окно дополнительно ведёт в окна
устройств AmneziaWG - они в ``vpn_awg.py``, но в том же диалоге.

Окно самодостаточно: пользователь берётся из ``dialog_manager.event.from_user``, все данные
грузит геттер. Диалог не полагается ни на middleware, ни на ``start_data`` - его можно открыть
из любого места, а доступ перепроверяется на каждой отрисовке (клавиатура у пользователя
могла устареть).
"""

from typing import Any

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Cancel, SwitchTo, Url
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.awg_access import get_access_by_person
from database.methods.person import get_person_with_member
from database.methods.vpn_subscription import get_subscription_by_person
from database.models import VpnSubscription
from dialogs.user.vpn_awg import awg_allowed, awg_windows
from includes.vpn import XuiError, ensure_subscription, get_xui_client
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from state_machines.vpn import ViewVpnSubscription
from utils import L10nFormat, current_member, escape_mdv2, format_traffic


# ========== Геттер: статус подписки ==========
async def get_vpn_data(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    **kwargs,
) -> dict[str, Any]:
    user = dialog_manager.event.from_user

    async with async_session() as session:
        person = await get_person_with_member(session, user.id)
        subscription = await get_subscription_by_person(session, person.id) if person else None
        access = await get_access_by_person(session, person.id) if person else None

    if current_member(person) is None:
        return {
            "is_allowed": False,
            "has_subscription": False,
            "awg_allowed": False,
            # Ключ живёт и в алерте (там разметки нет), поэтому в ftl он без экранирования.
            "text": escape_mdv2(l10n.format_value("vpn-access-denied-alert")),
        }

    data = await _get_subscription_data(subscription, person.id, l10n, log)

    data["awg_allowed"] = awg_allowed(access)
    if data["awg_allowed"]:
        data["text"] += "\n\n" + l10n.format_value("vpn-awg-hint")
    return data


async def _get_subscription_data(
    subscription: VpnSubscription | None,
    person_id: int,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
) -> dict[str, Any]:
    """Состояние VLESS-подписки мембера: текст окна и признаки для кнопок."""
    if subscription is None:
        return {
            "is_allowed": True,
            "has_subscription": False,
            "text": l10n.format_value("vpn-none"),
        }

    client = get_xui_client()
    try:
        traffic = await client.get_traffic(subscription.xui_email)
    except XuiError as exc:
        await log.aerror("vpn-status-failed", person_id=person_id, error=str(exc))
        return {"is_allowed": True, "has_subscription": True, "text": escape_mdv2(l10n.format_value("vpn-error-alert"))}

    if traffic is None:
        # Панель на удалённого клиента отвечает success=true с пустым obj.
        # Запись в БД осиротела: показываем это честно и предлагаем выпустить ключ заново.
        await log.awarning("vpn-client-missing", person_id=person_id, email=subscription.xui_email)
        return {
            "is_allowed": True,
            "has_subscription": False,
            "text": l10n.format_value("vpn-orphaned"),
        }

    text = l10n.format_value(
        "vpn-active" if traffic.enable else "vpn-disabled",
        args={
            "url": escape_mdv2(client.build_subscription_url(subscription.sub_id)),
            "traffic": escape_mdv2(format_traffic(traffic.used_bytes)),
        },
    )
    return {"is_allowed": True, "has_subscription": True, "text": text}


# ========== Хэндлер: выпуск или восстановление подписки ==========
async def on_issue(
    clb: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    # В on_click, в отличие от геттера, middleware-данные аргументами не приходят.
    l10n: FluentLocalization = dialog_manager.middleware_data[L10N_FORMAT_KEY]
    log: FilteringBoundLogger = dialog_manager.middleware_data[LOGGING_KEY]

    client = get_xui_client()

    try:
        async with async_session() as session:
            person = await get_person_with_member(session, clb.from_user.id)
            member = current_member(person)

            if member is None:
                await clb.answer(l10n.format_value("vpn-access-denied-alert"), show_alert=True)
                return

            # Всё сведение расхождений с панелью - внутри ensure_subscription.
            await ensure_subscription(session, client, person, member)
            await session.commit()
    except XuiError as exc:
        await log.aerror("vpn-issue-failed", telegram_id=clb.from_user.id, error=str(exc))
        await clb.answer(l10n.format_value("vpn-error-alert"), show_alert=True)
        return

    await clb.answer(l10n.format_value("vpn-issued-alert"))


# ========== Диалог ==========
vpn_dialog = Dialog(
    Window(
        Format("{text}"),
        Button(
            L10nFormat("vpn-issue-btn"),
            id="issue_vpn",
            on_click=on_issue,
            when=F["is_allowed"] & ~F["has_subscription"],
        ),
        # Обработанный клик в приватном чате сам вызывает перерисовку окна,
        # а геттер на каждой отрисовке ходит в панель - своего on_click кнопке не нужно.
        Button(
            L10nFormat("vpn-refresh-btn"),
            id="refresh_vpn",
            when=F["is_allowed"] & F["has_subscription"],
        ),
        SwitchTo(
            L10nFormat("vpn-awg-btn"),
            id="awg_devices",
            state=ViewVpnSubscription.AWG,
            when=F["is_allowed"] & F["awg_allowed"],
        ),
        Url(
            L10nFormat("vpn-handbook-btn"),
            L10nFormat("vpn-handbook-url"),
            when=F["is_allowed"],
        ),
        Cancel(L10nFormat("back-btn")),
        getter=get_vpn_data,
        state=ViewVpnSubscription.VIEW,
    ),
    *awg_windows,
)
