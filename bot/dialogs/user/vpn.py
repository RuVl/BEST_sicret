"""Поддиалог VPN: AmneziaWG (основной протокол) и VLESS-подписка (запасной).

Источник правды по состоянию ключей - панель 3x-ui; в БД бота лежат только идентификаторы.

Окно ведёт в окна устройств AmneziaWG - они в ``vpn_awg.py``, но в том же диалоге - и само
показывает VLESS-подписку: статус, выпуск, ссылку и трафик.

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
from best_db.models import VpnSubscription
from fluent.runtime import FluentLocalization
from sqlalchemy.exc import IntegrityError
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.awg_access import get_access_by_person
from database.methods.person import get_person_with_member
from database.methods.vpn_subscription import get_subscription_by_person
from dialogs.user.vpn_awg import awg_allowed, awg_windows
from env import settings
from includes.vpn import PANEL_ERRORS, ensure_subscription, get_xui_api, panel_error_text, subscription_url
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
            "text": l10n.format_value("vpn-access-denied"),
        }

    if settings.xui.ENABLED:
        data = {"can_issue": True, "can_restore": False} | await _get_subscription_data(
            subscription, person.id, l10n, log
        )
    else:
        # Панель не настроена: в неё не ходим и выпустить ничего не предлагаем.
        data = {
            "is_allowed": True,
            "has_subscription": False,
            "can_issue": False,
            "can_restore": False,
            "text": l10n.format_value("vpn-not-configured"),
        }

    data["awg_allowed"] = awg_allowed(access)
    if data["awg_allowed"]:
        # AmneziaWG - основной протокол, поэтому его подсказка идёт первой, а VLESS - запасным ниже.
        data["text"] = l10n.format_value("vpn-awg-hint") + "\n\n" + data["text"]
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

    try:
        traffic = await get_xui_api().client.get_traffic(subscription.xui_email)
    except PANEL_ERRORS as exc:
        await log.aerror("vpn-status-failed", person_id=person_id, error=panel_error_text(exc))
        return {"is_allowed": True, "has_subscription": True, "text": l10n.format_value("vpn-error")}

    if traffic is None:
        # Панель на удалённого клиента отвечает success=true с пустым obj.
        # Запись в БД осиротела: показываем это честно и предлагаем выпустить ключ заново.
        await log.awarning("vpn-client-missing", person_id=person_id, email=subscription.xui_email)
        return {
            "is_allowed": True,
            "has_subscription": False,
            "text": l10n.format_value("vpn-orphaned"),
        }

    # Отключил джоб, а человек снова мембер (окно открыто только мемберам) - включить может сам.
    # Выключенного в панели руками при живой подписке оставляем админу.
    can_restore = subscription.status != "active"
    state = "revoked" if can_restore else "active" if traffic.enable else "disabled"
    text = l10n.format_value(
        f"vpn-{state}",
        args={
            "url": escape_mdv2(subscription_url(subscription.sub_id)),
            # Счётчики с последнего сброса: панель обнуляет их раз в XUI_TRAFFIC_RESET_DAYS дней.
            "traffic": escape_mdv2(format_traffic(traffic.up + traffic.down)),
        },
    )
    return {"is_allowed": True, "has_subscription": True, "can_restore": can_restore, "text": text}


# ========== Хэндлер: выпуск или восстановление подписки ==========
async def on_issue(
    clb: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    # В on_click, в отличие от геттера, middleware-данные аргументами не приходят.
    l10n: FluentLocalization = dialog_manager.middleware_data[L10N_FORMAT_KEY]
    log: FilteringBoundLogger = dialog_manager.middleware_data[LOGGING_KEY]

    # Клавиатура могла устареть: кнопку нарисовали до того, как панель отключили в настройках.
    if not settings.xui.ENABLED:
        await clb.answer(l10n.format_value("vpn-not-configured-alert"), show_alert=True)
        return

    try:
        async with async_session() as session:
            person = await get_person_with_member(session, clb.from_user.id)
            member = current_member(person)

            if member is None:
                await clb.answer(l10n.format_value("vpn-access-denied-alert"), show_alert=True)
                return

            # Всё сведение расхождений с панелью - внутри ensure_subscription.
            await ensure_subscription(session, get_xui_api(), person, member)
            await session.commit()
    except (*PANEL_ERRORS, IntegrityError) as exc:
        # IntegrityError - двойной клик или чужая строка с теми же идентификаторами: сессия
        # откатится сама, а человек получит ответ вместо зависшей кнопки.
        await log.aerror("vpn-issue-failed", telegram_id=clb.from_user.id, error=panel_error_text(exc))
        await clb.answer(l10n.format_value("vpn-error-alert"), show_alert=True)
        return

    alert = "vpn-restored-alert" if widget.widget_id == "restore_vpn" else "vpn-issued-alert"
    await clb.answer(l10n.format_value(alert))


# ========== Диалог ==========
vpn_dialog = Dialog(
    Window(
        Format("{text}"),
        SwitchTo(
            L10nFormat("vpn-awg-btn"),
            id="awg_devices",
            state=ViewVpnSubscription.AWG,
            when=F["is_allowed"] & F["awg_allowed"],
        ),
        Button(
            L10nFormat("vpn-issue-btn"),
            id="issue_vpn",
            on_click=on_issue,
            when=F["is_allowed"] & F["can_issue"] & ~F["has_subscription"],
        ),
        # Тот же ensure_subscription: он и включает отключённого джобом клиента по прежней ссылке.
        Button(
            L10nFormat("vpn-restore-btn"),
            id="restore_vpn",
            on_click=on_issue,
            when=F["is_allowed"] & F["can_restore"],
        ),
        # Обработанный клик в приватном чате сам вызывает перерисовку окна,
        # а геттер на каждой отрисовке ходит в панель - своего on_click кнопке не нужно.
        Button(
            L10nFormat("vpn-refresh-btn"),
            id="refresh_vpn",
            when=F["is_allowed"] & F["has_subscription"],
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
