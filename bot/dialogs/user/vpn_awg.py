"""Окна устройств AmneziaWG внутри диалога VPN-подписки.

Один ключ AmneziaWG - одно устройство (в отличие от VLESS, где одна ссылка работает на
нескольких), поэтому человек заводит ключ на каждое устройство в пределах лимита, называет
его сам и видит по нему статус и трафик из веб-панели AmneziaWG.

Конфиг - это приватный ключ, поэтому он не уходит отдельными сообщениями: он показывается
окном диалога (файл или QR-код с кнопками) и исчезает из чата, когда человек уходит из окна,
жмёт «Готово» или истекает ``AWG_CONFIG_TTL_SECONDS``.

Как и окно VLESS, окна самодостаточны: членство и разрешение перепроверяются на каждой
отрисовке и каждом клике - клавиатура у пользователя могла устареть.
"""

import asyncio
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import BufferedInputFile, CallbackQuery, ContentType, Message
from aiogram_dialog import BaseDialogManager, DialogManager, ShowMode, Window
from aiogram_dialog.api.entities import MediaAttachment, MediaId
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Column, Select, SwitchTo
from aiogram_dialog.widgets.media import DynamicMedia
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
    MAX_DEVICE_LABEL_LEN,
    AwgAccessRevokedError,
    AwgDeviceLimitError,
    AwgError,
    AwgPeer,
    AwgUsagePeriod,
    AwgUsageSummary,
    add_device,
    device_limit,
    get_awg_client,
    issue_device_config,
    normalize_device_label,
    peers_by_name,
    remove_device,
    rename_device,
    render_config_qr,
    restore_access,
)
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from state_machines.vpn import ViewVpnSubscription
from utils import L10nFormat, current_member, escape_mdv2, format_traffic

logger: FilteringBoundLogger = structlog.get_logger("awg-dialog")

# Время последнего подключения показываем по Москве - как и всё расписание бота.
_DISPLAY_TZ = ZoneInfo("Europe/Moscow")

# Ключи dialog_data
_DEVICE = "awg_device"  # номер открытого устройства
_NAME_TARGET = "awg_name_target"  # None - новое устройство, число - переименование
_NAME_ERROR = "awg_name_error"  # готовый текст ошибки под вопросом о названии
_CONFIG = "awg_config"  # file_id файла и QR открытого конфига
_SHOW_QR = "awg_show_qr"
_HIDDEN = "awg_hidden"  # токен конфига, который убрал таймер

# Таймеры автоскрытия: держим ссылки, иначе event loop может собрать задачу до срабатывания.
_hide_tasks: set[asyncio.Task] = set()


# ========== Общие помощники ==========
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


def _find_device(access: AwgAccess, number: int | None) -> AwgDevice | None:
    return next((device for device in access.devices if device.number == number), None)


def _device_name(l10n: FluentLocalization, device: AwgDevice) -> str:
    return device.label or l10n.format_value("vpn-awg-device-default-name", args={"number": device.number})


def _device_status(l10n: FluentLocalization, peer: AwgPeer | None, peers_known: bool) -> str:
    if not peers_known:
        return l10n.format_value("vpn-awg-status-unknown")
    if peer is None:
        return l10n.format_value("vpn-awg-status-missing")
    if peer.connection_status in ("online", "inactive", "never", "disabled"):
        return l10n.format_value(f"vpn-awg-status-{peer.connection_status}")
    return l10n.format_value("vpn-awg-status-unknown")


def _format_handshake(l10n: FluentLocalization, moment: datetime | None) -> str:
    if moment is None:
        return l10n.format_value("vpn-awg-handshake-never")
    return moment.astimezone(_DISPLAY_TZ).strftime("%d.%m.%Y %H:%M")


def _format_period(l10n: FluentLocalization, period: AwgUsagePeriod | None) -> str:
    """«скачано / отправлено» глазами человека: панель считает со стороны сервера, поэтому tx - это скачано."""
    if period is None:
        return l10n.format_value("vpn-awg-no-data")
    return l10n.format_value(
        "vpn-awg-traffic",
        args={"down": format_traffic(period.tx_bytes), "up": format_traffic(period.rx_bytes)},
    )


def _middleware(dialog_manager: DialogManager) -> tuple[FluentLocalization, FilteringBoundLogger]:
    # В хэндлерах, в отличие от геттера, middleware-данные аргументами не приходят.
    return dialog_manager.middleware_data[L10N_FORMAT_KEY], dialog_manager.middleware_data[LOGGING_KEY]


def _awg_error_text(l10n: FluentLocalization, exc: AwgError, access: AwgAccess | None) -> str:
    if isinstance(exc, AwgDeviceLimitError) and access is not None:
        return l10n.format_value("vpn-awg-limit", args={"used": len(access.devices), "limit": device_limit(access)})
    if isinstance(exc, AwgAccessRevokedError):
        return l10n.format_value("vpn-awg-denied")
    return l10n.format_value("vpn-awg-error")


async def _delete_quietly(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramAPIError as exc:
        await logger.awarning("awg-message-delete-failed", chat_id=chat_id, error=str(exc))


# ========== Конфиг: загрузка в Telegram и автоскрытие ==========
async def _upload(bot: Bot, chat_id: int, config: str, filename: str) -> tuple[str, str | None]:
    """Получить ``file_id`` файла и QR, чтобы показать их окном диалога.

    aiogram-dialog умеет показывать медиа только по ``file_id``/пути/URL, а конфиг не должен
    ложиться на диск. Поэтому отправляем файл беззвучно и сразу удаляем это сообщение -
    ``file_id`` остаётся рабочим.
    """
    sent = await bot.send_document(
        chat_id, BufferedInputFile(config.encode(), filename=filename), disable_notification=True
    )
    await _delete_quietly(bot, chat_id, sent.message_id)
    document_id = sent.document.file_id

    try:
        qr = render_config_qr(config)
    except ValueError as exc:
        # Конфиг с длинными I1-I5 может не влезть в QR - файла достаточно.
        await logger.awarning("awg-qr-failed", chat_id=chat_id, error=str(exc))
        return document_id, None

    sent = await bot.send_photo(chat_id, BufferedInputFile(qr, filename="amneziawg-qr.png"), disable_notification=True)
    await _delete_quietly(bot, chat_id, sent.message_id)
    return document_id, sent.photo[-1].file_id


async def _hide_later(bg: BaseDialogManager, token: str) -> None:
    await asyncio.sleep(settings.awg.CONFIG_TTL_SECONDS)
    try:
        # Окно конфига по этому токену поймёт, что пора убрать файл; другие окна ключ проигнорируют.
        await bg.update({_HIDDEN: token})
    except Exception as exc:
        # Фоновая задача: исключение некому поймать, поэтому только пишем в лог.
        await logger.awarning("awg-config-hide-failed", error=str(exc))


async def _open_config(dialog_manager: DialogManager, device: AwgDevice, name: str, config: str) -> None:
    """Показать конфиг окном и завести таймер, который уберёт его из чата."""
    event = dialog_manager.event
    file_id, qr_id = await _upload(
        event.bot, event.from_user.id, config, f"{settings.awg.TUNNEL_NAME}-{device.number}.conf"
    )

    token = uuid4().hex
    dialog_manager.dialog_data[_CONFIG] = {"token": token, "file": file_id, "qr": qr_id, "name": name}
    dialog_manager.dialog_data[_SHOW_QR] = False

    # Привязка к стеку, а не к окну: если человек к тому времени закрыл диалог, обновление
    # не упадёт с UnknownIntent (а его хэндлер сбросил бы человеку меню).
    bg = dialog_manager.bg(stack_id=dialog_manager.current_stack().id)
    task = asyncio.create_task(_hide_later(bg, token))
    _hide_tasks.add(task)
    task.add_done_callback(_hide_tasks.discard)

    # Текстовое сообщение в медиа не отредактировать - старое окно удаляем и шлём новое.
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_CONFIG, show_mode=ShowMode.DELETE_AND_SEND)


# ========== Геттеры ==========
_DENIED: dict[str, Any] = {
    "is_allowed": False,
    "can_add": False,
    "is_suspended": False,
    "devices": [],
    "has_device": False,
    "has_peer": False,
}


async def get_awg_data(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    **kwargs,
) -> dict[str, Any]:
    async with async_session() as session:
        loaded = await _load_access(session, dialog_manager.event.from_user.id)

    if loaded is None:
        return _DENIED | {"text": escape_mdv2(l10n.format_value("vpn-awg-denied"))}
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
                "name": _device_name(l10n, device),
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

    return _DENIED | {
        "is_allowed": True,
        "can_add": len(access.devices) < limit,
        "is_suspended": is_suspended,
        "devices": [(_device_name(l10n, device), device.number) for device in access.devices],
        "text": text,
    }


async def get_device_data(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    **kwargs,
) -> dict[str, Any]:
    async with async_session() as session:
        loaded = await _load_access(session, dialog_manager.event.from_user.id)
    device = _find_device(loaded[1], dialog_manager.dialog_data.get(_DEVICE)) if loaded else None

    if loaded is None or device is None:
        return _DENIED | {"text": escape_mdv2(l10n.format_value("vpn-awg-denied"))}

    peer: AwgPeer | None = None
    usage: AwgUsageSummary | None = None
    panel_ok = True
    client = get_awg_client()
    try:
        peer = await client.find_peer(device.client_name)
        if peer is not None:
            usage = await client.get_usage_summary(peer.id)
    except AwgError as exc:
        await log.aerror("vpn-awg-stats-failed", person_id=loaded[0].id, number=device.number, error=str(exc))
        panel_ok = False

    no_data = l10n.format_value("vpn-awg-no-data")
    text = l10n.format_value(
        "vpn-awg-device-card",
        args={
            "name": escape_mdv2(_device_name(l10n, device)),
            "status": escape_mdv2(_device_status(l10n, peer, panel_ok)),
            "handshake": escape_mdv2(_format_handshake(l10n, peer.latest_handshake_at) if peer else no_data),
            "day": escape_mdv2(_format_period(l10n, usage.day if usage else None)),
            "week": escape_mdv2(_format_period(l10n, usage.week if usage else None)),
            "month": escape_mdv2(_format_period(l10n, usage.month if usage else None)),
        },
    )
    if not panel_ok:
        text += "\n\n" + l10n.format_value("vpn-awg-panel-error-hint")

    return _DENIED | {"is_allowed": True, "has_device": True, "text": text}


async def get_name_data(dialog_manager: DialogManager, l10n: FluentLocalization, **kwargs) -> dict[str, Any]:
    target = dialog_manager.dialog_data.get(_NAME_TARGET)
    if target is None:
        text = l10n.format_value("vpn-awg-name-new", args={"max": MAX_DEVICE_LABEL_LEN})
    else:
        async with async_session() as session:
            loaded = await _load_access(session, dialog_manager.event.from_user.id)
        device = _find_device(loaded[1], target) if loaded else None
        name = _device_name(l10n, device) if device else ""
        text = l10n.format_value("vpn-awg-name-rename", args={"name": escape_mdv2(name), "max": MAX_DEVICE_LABEL_LEN})

    error = dialog_manager.dialog_data.get(_NAME_ERROR)
    if error:
        text += "\n\n" + escape_mdv2(error)
    return {"text": text}


async def get_config_data(dialog_manager: DialogManager, l10n: FluentLocalization, **kwargs) -> dict[str, Any]:
    config = dialog_manager.dialog_data.get(_CONFIG)
    if config is not None and dialog_manager.dialog_data.get(_HIDDEN) == config["token"]:
        # Сработал таймер: забываем file_id, окно без медиа - aiogram-dialog удалит сообщение с файлом.
        dialog_manager.dialog_data.pop(_CONFIG, None)
        config = None

    if config is None:
        return {
            "show_media": False,
            "has_qr": False,
            "show_qr": False,
            "text": l10n.format_value("vpn-awg-config-hidden"),
        }

    show_qr = bool(dialog_manager.dialog_data.get(_SHOW_QR)) and config["qr"] is not None
    media = MediaAttachment(
        ContentType.PHOTO if show_qr else ContentType.DOCUMENT,
        file_id=MediaId(config["qr"] if show_qr else config["file"]),
    )
    args = {"name": escape_mdv2(config["name"]), "minutes": max(1, settings.awg.CONFIG_TTL_SECONDS // 60)}
    return {
        "show_media": True,
        "media": media,
        "has_qr": config["qr"] is not None,
        "show_qr": show_qr,
        "text": l10n.format_value("vpn-awg-qr-caption" if show_qr else "vpn-awg-config-caption", args=args),
    }


async def get_delete_data(dialog_manager: DialogManager, l10n: FluentLocalization, **kwargs) -> dict[str, Any]:
    async with async_session() as session:
        loaded = await _load_access(session, dialog_manager.event.from_user.id)
    device = _find_device(loaded[1], dialog_manager.dialog_data.get(_DEVICE)) if loaded else None
    name = _device_name(l10n, device) if device else ""
    return {"text": l10n.format_value("vpn-awg-delete-confirm", args={"name": escape_mdv2(name)})}


# ========== Хэндлеры: список ==========
async def on_select_device(clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, item_id: str) -> None:
    dialog_manager.dialog_data[_DEVICE] = int(item_id)
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)


async def on_start_add(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    l10n, _ = _middleware(dialog_manager)
    async with async_session() as session:
        loaded = await _load_access(session, clb.from_user.id)

    if loaded is None:
        await clb.answer(l10n.format_value("vpn-awg-denied"), show_alert=True)
        return
    # Лимит проверяем до вопроса о названии, чтобы человек не печатал его зря.
    access = loaded[1]
    if len(access.devices) >= device_limit(access):
        await clb.answer(_awg_error_text(l10n, AwgDeviceLimitError(), access), show_alert=True)
        return

    dialog_manager.dialog_data[_NAME_TARGET] = None
    dialog_manager.dialog_data.pop(_NAME_ERROR, None)
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_NAME)


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


# ========== Хэндлеры: карточка устройства ==========
async def on_get_config(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    l10n, log = _middleware(dialog_manager)
    number = dialog_manager.dialog_data.get(_DEVICE)
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
        await clb.answer(_awg_error_text(l10n, exc, access), show_alert=True)
        return

    await clb.answer()
    await _open_config(dialog_manager, device, _device_name(l10n, device), config)


async def on_start_rename(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data[_NAME_TARGET] = dialog_manager.dialog_data.get(_DEVICE)
    dialog_manager.dialog_data.pop(_NAME_ERROR, None)
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_NAME)


async def on_delete_confirmed(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    l10n, log = _middleware(dialog_manager)
    number = dialog_manager.dialog_data.get(_DEVICE)

    try:
        async with async_session() as session:
            loaded = await _load_access(session, clb.from_user.id)
            device = _find_device(loaded[1], number) if loaded else None
            # Устройство могли уже удалить из другого окна - удалять нечего, просто возвращаемся.
            if device is not None:
                await remove_device(session, get_awg_client(), loaded[1], device)
                await session.commit()
    except AwgError as exc:
        await log.aerror("vpn-awg-delete-failed", telegram_id=clb.from_user.id, number=number, error=str(exc))
        await clb.answer(l10n.format_value("vpn-awg-error"), show_alert=True)
        await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)
        return

    dialog_manager.dialog_data.pop(_DEVICE, None)
    await clb.answer(l10n.format_value("vpn-awg-deleted"))
    await dialog_manager.switch_to(ViewVpnSubscription.AWG)


# ========== Хэндлеры: название ==========
async def on_name_entered(
    message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, label: str
) -> None:
    l10n, log = _middleware(dialog_manager)
    # Сообщение с названием убираем, чтобы окно диалога осталось последним и редактировалось на месте.
    await _delete_quietly(message.bot, message.chat.id, message.message_id)
    dialog_manager.show_mode = ShowMode.EDIT

    target = dialog_manager.dialog_data.get(_NAME_TARGET)
    access: AwgAccess | None = None
    try:
        async with async_session() as session:
            loaded = await _load_access(session, message.from_user.id)
            if loaded is None:
                await dialog_manager.switch_to(ViewVpnSubscription.AWG)
                return
            person, access = loaded
            client = get_awg_client()

            if target is None:
                device, config = await add_device(session, client, access, person, label)
                await session.commit()
            else:
                device = _find_device(access, target)
                if device is not None:
                    await rename_device(session, client, device, person, label)
                    await session.commit()
                config = None
    except AwgError as exc:
        await log.aerror("vpn-awg-name-failed", telegram_id=message.from_user.id, target=target, error=str(exc))
        dialog_manager.dialog_data[_NAME_ERROR] = _awg_error_text(l10n, exc, access)
        return

    dialog_manager.dialog_data.pop(_NAME_ERROR, None)
    dialog_manager.dialog_data.pop(_NAME_TARGET, None)
    if config is None:
        await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)
        return

    dialog_manager.dialog_data[_DEVICE] = device.number
    await _open_config(dialog_manager, device, label, config)


async def on_name_error(message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, error: ValueError):
    l10n, _ = _middleware(dialog_manager)
    await _delete_quietly(message.bot, message.chat.id, message.message_id)
    dialog_manager.show_mode = ShowMode.EDIT
    dialog_manager.dialog_data[_NAME_ERROR] = l10n.format_value(
        "vpn-awg-name-invalid", args={"max": MAX_DEVICE_LABEL_LEN}
    )


async def on_name_back(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data.pop(_NAME_ERROR, None)
    target = dialog_manager.dialog_data.pop(_NAME_TARGET, None)
    state = ViewVpnSubscription.AWG if target is None else ViewVpnSubscription.AWG_DEVICE
    await dialog_manager.switch_to(state)


# ========== Хэндлеры: конфиг ==========
async def on_toggle_qr(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data[_SHOW_QR] = not dialog_manager.dialog_data.get(_SHOW_QR, False)


async def on_config_done(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    # Без медиа окно не отредактировать - aiogram-dialog удалит сообщение с файлом и пришлёт карточку.
    dialog_manager.dialog_data.pop(_CONFIG, None)
    dialog_manager.dialog_data.pop(_SHOW_QR, None)
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)


# ========== Окна ==========
awg_windows = (
    # --- Список устройств ---
    Window(
        Format("{text}"),
        Button(
            L10nFormat("vpn-awg-restore-btn"),
            id="awg_restore",
            on_click=on_restore,
            when=F["is_allowed"] & F["is_suspended"],
        ),
        Column(
            Select(
                Format("{item[0]}"),
                id="awg_devices",
                item_id_getter=lambda item: item[1],
                items="devices",
                on_click=on_select_device,
            ),
        ),
        Button(
            L10nFormat("vpn-awg-add-btn"),
            id="awg_add",
            on_click=on_start_add,
            when=F["is_allowed"] & F["can_add"],
        ),
        SwitchTo(L10nFormat("back"), id="awg_back", state=ViewVpnSubscription.VIEW),
        getter=get_awg_data,
        state=ViewVpnSubscription.AWG,
    ),
    # --- Карточка устройства ---
    Window(
        Format("{text}"),
        Button(L10nFormat("vpn-awg-get-config-btn"), id="awg_get_config", on_click=on_get_config, when="has_device"),
        Button(L10nFormat("vpn-awg-rename-btn"), id="awg_rename", on_click=on_start_rename, when="has_device"),
        SwitchTo(
            L10nFormat("vpn-awg-delete-btn"),
            id="awg_delete",
            state=ViewVpnSubscription.AWG_DELETE,
            when="has_device",
        ),
        SwitchTo(L10nFormat("back"), id="awg_device_back", state=ViewVpnSubscription.AWG),
        getter=get_device_data,
        state=ViewVpnSubscription.AWG_DEVICE,
    ),
    # --- Название ---
    Window(
        Format("{text}"),
        TextInput(
            id="awg_name",
            type_factory=normalize_device_label,
            on_success=on_name_entered,
            on_error=on_name_error,
        ),
        Button(L10nFormat("back"), id="awg_name_back", on_click=on_name_back),
        getter=get_name_data,
        state=ViewVpnSubscription.AWG_NAME,
    ),
    # --- Конфиг: файл или QR в одном сообщении с кнопками ---
    Window(
        DynamicMedia("media", when="show_media"),
        Format("{text}"),
        Button(
            L10nFormat("vpn-awg-show-qr-btn"),
            id="awg_show_qr",
            on_click=on_toggle_qr,
            when=F["has_qr"] & ~F["show_qr"],
        ),
        Button(L10nFormat("vpn-awg-show-file-btn"), id="awg_show_file", on_click=on_toggle_qr, when="show_qr"),
        Button(L10nFormat("vpn-awg-done-btn"), id="awg_config_done", on_click=on_config_done),
        getter=get_config_data,
        state=ViewVpnSubscription.AWG_CONFIG,
    ),
    # --- Подтверждение удаления ---
    Window(
        Format("{text}"),
        Button(L10nFormat("vpn-awg-delete-yes-btn"), id="awg_delete_yes", on_click=on_delete_confirmed),
        SwitchTo(L10nFormat("back"), id="awg_delete_back", state=ViewVpnSubscription.AWG_DEVICE),
        getter=get_delete_data,
        state=ViewVpnSubscription.AWG_DELETE,
    ),
)
