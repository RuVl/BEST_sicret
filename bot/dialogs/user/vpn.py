"""Поддиалог VPN-подписки: статус, выпуск, ссылка и трафик.

Источник правды по состоянию ключа - панель 3x-ui; в БД бота лежат только идентификаторы.

Окно самодостаточно: пользователь берётся из ``dialog_manager.event.from_user``, все данные
грузит геттер. Диалог не полагается ни на middleware, ни на ``start_data`` - его можно открыть
из любого места, а доступ перепроверяется на каждой отрисовке (клавиатура у пользователя
могла устареть).
"""

from typing import Any

from aiogram import F
from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.kbd import Button, Cancel, Url
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.person import get_person_with_member
from database.methods.vpn_subscription import get_subscription_by_person
from includes.vpn import XuiError, ensure_subscription, get_xui_client
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from state_machines.vpn import ViewVpnSubscription
from utils import L10nFormat, current_member, escape_mdv2


def _format_traffic(used_bytes: int) -> str:
    """Байты в читаемый вид: до гигабайта - мегабайты, дальше гигабайты."""
    _GB = 1024**3
    if used_bytes < _GB:
        return f"{used_bytes / 1024**2:.1f} МБ"
    return f"{used_bytes / _GB:.2f} ГБ"


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

    if current_member(person) is None:
        return {
            "is_allowed": False,
            "has_subscription": False,
            # Ключ живёт и в алерте (там разметки нет), поэтому в ftl он без экранирования.
            "text": escape_mdv2(l10n.format_value("vpn-access-denied")),
        }

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
        await log.aerror("vpn-status-failed", person_id=person.id, error=str(exc))
        return {"is_allowed": True, "has_subscription": True, "text": escape_mdv2(l10n.format_value("vpn-error"))}

    if traffic is None:
        # Панель на удалённого клиента отвечает success=true с пустым obj.
        # Запись в БД осиротела: показываем это честно и предлагаем выпустить ключ заново.
        await log.awarning("vpn-client-missing", person_id=person.id, email=subscription.xui_email)
        return {
            "is_allowed": True,
            "has_subscription": False,
            "text": l10n.format_value("vpn-orphaned"),
        }

    text = l10n.format_value(
        "vpn-active" if traffic.enable else "vpn-disabled",
        args={
            "url": escape_mdv2(client.build_subscription_url(subscription.sub_id)),
            "traffic": escape_mdv2(_format_traffic(traffic.used_bytes)),
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
                await clb.answer(l10n.format_value("vpn-access-denied"), show_alert=True)
                return

            # Всё сведение расхождений с панелью - внутри ensure_subscription.
            await ensure_subscription(session, client, person, member)
            await session.commit()
    except XuiError as exc:
        await log.aerror("vpn-issue-failed", telegram_id=clb.from_user.id, error=str(exc))
        await clb.answer(l10n.format_value("vpn-error"), show_alert=True)
        return

    await clb.answer(l10n.format_value("vpn-issued"))


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
        Url(
            L10nFormat("vpn-handbook-btn"),
            L10nFormat("vpn-handbook-url"),
            when=F["is_allowed"],
        ),
        Cancel(L10nFormat("back")),
        getter=get_vpn_data,
        state=ViewVpnSubscription.VIEW,
    ),
)
