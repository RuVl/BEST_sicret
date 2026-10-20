"""Окна устройств AmneziaWG внутри диалога VPN-подписки.

Один ключ AmneziaWG - одно устройство (в отличие от VLESS, где одна ссылка работает на
нескольких), поэтому человек заводит ключ на каждое устройство в пределах лимита и получает
конфиг файлом и QR-кодом. Ключи живут в веб-панели AmneziaWG, в БД бота - только номера
устройств и имена клиентов.

Как и окно VLESS, окна самодостаточны: членство и разрешение перепроверяются на каждой
отрисовке и каждом клике - клавиатура у пользователя могла устареть.
"""

from typing import Any

from aiogram import F
from aiogram.types import BufferedInputFile, CallbackQuery
from aiogram_dialog import DialogManager, ShowMode, Window
from aiogram_dialog.widgets.kbd import Button, Group, Select, SwitchTo
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.awg_access import get_access_by_person
from database.methods.person import get_person_with_member
from database.models import AwgAccess, AwgDevice, Person
from env import settings
from includes.awg import (
    AwgAccessRevokedError,
    AwgDeviceLimitError,
    AwgError,
    AwgPeer,
    add_device,
    device_limit,
    get_awg_client,
    issue_device_config,
    peers_by_name,
    remove_device,
    render_config_qr,
    restore_access,
)
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from state_machines.vpn import ViewVpnSubscription
from utils import L10nFormat, current_member, escape_mdv2

# Ключ dialog_data: номер устройства, которое ждёт подтверждения удаления.
_DELETE_KEY = "awg_delete_number"


def awg_allowed(access: AwgAccess | None) -> bool:
    """Окно AmneziaWG: разрешение есть и не отозвано админом (``suspended`` оживает по кнопке)."""
    return settings.awg.ENABLED and access is not None and access.status != "revoked"


async def _load_access(session: AsyncSession, telegram_id: int) -> tuple[Person, AwgAccess] | None:
    """Человек и его разрешение - или ``None``, если доступа к AmneziaWG у него сейчас нет."""
    person = await get_person_with_member(session, telegram_id)
    if current_member(person) is None:
        return None
    access = await get_access_by_person(session, person.id)
    if not awg_allowed(access):
        return None
    return person, access


def _find_device(access: AwgAccess, number: int) -> AwgDevice | None:
    return next((device for device in access.devices if device.number == number), None)


def _device_status(l10n: FluentLocalization, peer: AwgPeer | None, peers_known: bool) -> str:
    if not peers_known:
        return l10n.format_value("vpn-awg-status-unknown")
    if peer is None:
        return l10n.format_value("vpn-awg-status-missing")
    if peer.connection_status in ("online", "inactive", "never", "disabled"):
        return l10n.format_value(f"vpn-awg-status-{peer.connection_status}")
    return l10n.format_value("vpn-awg-status-unknown")


def _middleware(dialog_manager: DialogManager) -> tuple[FluentLocalization, FilteringBoundLogger]:
    # В on_click, в отличие от геттера, middleware-данные аргументами не приходят.
    return dialog_manager.middleware_data[L10N_FORMAT_KEY], dialog_manager.middleware_data[LOGGING_KEY]


async def _send_config(
    clb: CallbackQuery,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    number: int,
    config: str,
) -> None:
    """Конфиг файлом и QR-кодом. Окно диалога затем переезжает под присланные сообщения."""
    args = {"number": number}
    await clb.bot.send_document(
        clb.from_user.id,
        BufferedInputFile(config.encode(), filename=f"{settings.awg.TUNNEL_NAME}-{number}.conf"),
        caption=l10n.format_value("vpn-awg-config-caption", args=args),
    )
    try:
        qr = render_config_qr(config)
    except ValueError as exc:
        # Конфиг с длинными I1-I5 может не влезть в QR - файла достаточно.
        await log.awarning("vpn-awg-qr-failed", telegram_id=clb.from_user.id, error=str(exc))
    else:
        await clb.bot.send_photo(
            clb.from_user.id,
            BufferedInputFile(qr, filename=f"amneziawg-{number}.png"),
            caption=l10n.format_value("vpn-awg-qr-caption"),
        )


async def _answer_awg_error(
    clb: CallbackQuery,
    l10n: FluentLocalization,
    exc: AwgError,
    access: AwgAccess | None,
) -> None:
    """Ошибку панели или лимита - в алерт; в лог пишет вызывающая сторона."""
    if isinstance(exc, AwgDeviceLimitError) and access is not None:
        text = l10n.format_value("vpn-awg-limit", args={"used": len(access.devices), "limit": device_limit(access)})
    elif isinstance(exc, AwgAccessRevokedError):
        text = l10n.format_value("vpn-awg-denied")
    else:
        text = l10n.format_value("vpn-awg-error")
    await clb.answer(text, show_alert=True)


# ========== Геттер: устройства ==========
async def get_awg_data(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    **kwargs,
) -> dict[str, Any]:
    async with async_session() as session:
        loaded = await _load_access(session, dialog_manager.event.from_user.id)

    if loaded is None:
        return {
            "is_allowed": False,
            "can_add": False,
            "is_suspended": False,
            "configs": [],
            "deletions": [],
            "text": escape_mdv2(l10n.format_value("vpn-awg-denied")),
        }
    person, access = loaded

    peers: dict[str, AwgPeer] = {}
    peers_known = True
    if access.devices:
        try:
            peers = await peers_by_name(get_awg_client())
        except AwgError as exc:
            await log.aerror("vpn-awg-status-failed", person_id=person.id, error=str(exc))
            peers_known = False

    lines = [
        l10n.format_value(
            "vpn-awg-device-line",
            args={
                "number": device.number,
                "status": _device_status(l10n, peers.get(device.client_name), peers_known),
            },
        )
        for device in access.devices
    ] or [l10n.format_value("vpn-awg-devices-empty")]

    limit = device_limit(access)
    text = l10n.format_value(
        "vpn-awg-devices",
        args={"used": len(access.devices), "limit": limit, "devices": escape_mdv2("\n".join(lines))},
    )
    is_suspended = access.status == "suspended"
    if is_suspended:
        text += "\n\n" + l10n.format_value("vpn-awg-suspended-hint")
    if not peers_known:
        text += "\n\n" + l10n.format_value("vpn-awg-panel-error-hint")

    numbers = [device.number for device in access.devices]
    return {
        "is_allowed": True,
        "can_add": len(access.devices) < limit,
        "is_suspended": is_suspended,
        "configs": [(l10n.format_value("vpn-awg-config-btn", args={"number": n}), n) for n in numbers],
        "deletions": [(l10n.format_value("vpn-awg-delete-btn", args={"number": n}), n) for n in numbers],
        "text": text,
    }


async def get_awg_delete_data(dialog_manager: DialogManager, l10n: FluentLocalization, **kwargs) -> dict[str, Any]:
    number = dialog_manager.dialog_data.get(_DELETE_KEY, 0)
    return {"text": l10n.format_value("vpn-awg-delete-confirm", args={"number": number})}


# ========== Хэндлеры ==========
async def on_add_device(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    l10n, log = _middleware(dialog_manager)
    access: AwgAccess | None = None

    try:
        async with async_session() as session:
            loaded = await _load_access(session, clb.from_user.id)
            if loaded is None:
                await clb.answer(l10n.format_value("vpn-awg-denied"), show_alert=True)
                return
            person, access = loaded

            device, config = await add_device(session, get_awg_client(), access, person)
            await session.commit()
    except AwgError as exc:
        await log.aerror("vpn-awg-add-failed", telegram_id=clb.from_user.id, error=str(exc))
        await _answer_awg_error(clb, l10n, exc, access)
        return

    await _send_config(clb, l10n, log, device.number, config)
    await clb.answer(l10n.format_value("vpn-awg-sent"))
    dialog_manager.show_mode = ShowMode.DELETE_AND_SEND


async def on_device_config(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str) -> None:
    l10n, log = _middleware(dialog_manager)
    number = int(item_id)
    access: AwgAccess | None = None

    try:
        async with async_session() as session:
            loaded = await _load_access(session, clb.from_user.id)
            device = _find_device(loaded[1], number) if loaded else None
            if loaded is None or device is None:
                await clb.answer(l10n.format_value("vpn-awg-denied"), show_alert=True)
                return
            person, access = loaded

            config = await issue_device_config(session, get_awg_client(), access, device, person)
            await session.commit()
    except AwgError as exc:
        await log.aerror("vpn-awg-issue-failed", telegram_id=clb.from_user.id, number=number, error=str(exc))
        await _answer_awg_error(clb, l10n, exc, access)
        return

    await _send_config(clb, l10n, log, number, config)
    await clb.answer(l10n.format_value("vpn-awg-sent"))
    dialog_manager.show_mode = ShowMode.DELETE_AND_SEND


async def on_device_delete(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str) -> None:
    dialog_manager.dialog_data[_DELETE_KEY] = int(item_id)
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_DELETE)


async def on_delete_confirmed(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    l10n, log = _middleware(dialog_manager)
    number = dialog_manager.dialog_data.pop(_DELETE_KEY, None)

    try:
        async with async_session() as session:
            loaded = await _load_access(session, clb.from_user.id)
            device = _find_device(loaded[1], number) if loaded and number is not None else None
            # Устройство могли уже удалить из другого окна - удалять нечего, просто возвращаемся.
            if device is not None:
                await remove_device(session, get_awg_client(), loaded[1], device)
                await session.commit()
    except AwgError as exc:
        await log.aerror("vpn-awg-delete-failed", telegram_id=clb.from_user.id, number=number, error=str(exc))
        await clb.answer(l10n.format_value("vpn-awg-error"), show_alert=True)
    else:
        await clb.answer(l10n.format_value("vpn-awg-deleted"))

    await dialog_manager.switch_to(ViewVpnSubscription.AWG)


async def on_restore(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    l10n, log = _middleware(dialog_manager)

    try:
        async with async_session() as session:
            loaded = await _load_access(session, clb.from_user.id)
            if loaded is None:
                await clb.answer(l10n.format_value("vpn-awg-denied"), show_alert=True)
                return
            if loaded[1].status == "suspended":
                await restore_access(session, get_awg_client(), loaded[1])
                await session.commit()
    except AwgError as exc:
        await log.aerror("vpn-awg-restore-failed", telegram_id=clb.from_user.id, error=str(exc))
        await clb.answer(l10n.format_value("vpn-awg-error"), show_alert=True)
        return

    await clb.answer(l10n.format_value("vpn-awg-restored"))


# ========== Окна ==========
awg_windows = (
    Window(
        Format("{text}"),
        Button(
            L10nFormat("vpn-awg-restore-btn"),
            id="awg_restore",
            on_click=on_restore,
            when=F["is_allowed"] & F["is_suspended"],
        ),
        Button(
            L10nFormat("vpn-awg-add-btn"),
            id="awg_add",
            on_click=on_add_device,
            when=F["is_allowed"] & F["can_add"],
        ),
        # Под каждым устройством - пара «конфиг / удалить».
        Group(
            Select(
                Format("{item[0]}"),
                id="awg_config",
                item_id_getter=lambda item: item[1],
                items="configs",
                on_click=on_device_config,
            ),
            width=3,
            when="configs",
        ),
        Group(
            Select(
                Format("{item[0]}"),
                id="awg_delete",
                item_id_getter=lambda item: item[1],
                items="deletions",
                on_click=on_device_delete,
            ),
            width=3,
            when="deletions",
        ),
        SwitchTo(L10nFormat("back"), id="awg_back", state=ViewVpnSubscription.VIEW),
        getter=get_awg_data,
        state=ViewVpnSubscription.AWG,
    ),
    Window(
        Format("{text}"),
        Button(L10nFormat("vpn-awg-delete-yes-btn"), id="awg_delete_yes", on_click=on_delete_confirmed),
        SwitchTo(L10nFormat("back"), id="awg_delete_back", state=ViewVpnSubscription.AWG),
        getter=get_awg_delete_data,
        state=ViewVpnSubscription.AWG_DELETE,
    ),
)
