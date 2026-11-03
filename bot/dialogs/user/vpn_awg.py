"""Окна устройств AmneziaWG внутри диалога VPN-подписки.

AmneziaWG - основной протокол, он открыт каждому активному мемберу LBG: разрешение заводится
само вместе с первым устройством, админ может только отозвать его или поменять лимит (``make awg-*``).

Один ключ AmneziaWG - одно устройство (в отличие от VLESS, где одна ссылка работает на
нескольких), поэтому человек заводит ключ на каждое устройство в пределах лимита, называет
его сам, указывает платформу (от неё зависит конфиг, см. ``includes.awg.platform``) и видит
по нему статус и трафик из панели 3x-ui.

Конфиг - это приватный ключ, поэтому он не уходит отдельными сообщениями: он показывается
окном диалога (файл или QR-код с кнопками) и исчезает из чата, когда человек жмёт «Готово»,
открывает другой конфиг или истекает ``AWG_CONFIG_TTL_SECONDS``. Байты файла и QR лежат только
в памяти бота (``includes.memory_media``). Каждое сообщение, в которое ушёл файл, учитывается,
и скрытие удаляет их все (``includes.config_hide``); незавершённые скрытия записаны в Redis и
добираются при старте бота.

Как и окно VLESS, окна самодостаточны: членство и разрешение перепроверяются на каждой
отрисовке и каждом клике - клавиатура у пользователя могла устареть.
"""

from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import structlog
from aiogram import Bot, F
from aiogram.exceptions import TelegramAPIError
from aiogram.types import CallbackQuery, ContentType, Message
from aiogram_dialog import DialogManager, ShowMode, Window
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Group, Row, Select, SwitchTo, Url
from aiogram_dialog.widgets.media import DynamicMedia
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.awg_access import create_access, get_access_by_person, set_device_platform
from database.methods.person import get_person_with_member
from database.models import AwgAccess, AwgDevice, Person
from env import settings
from includes.awg import (
    MAX_DEVICE_LABEL_LEN,
    AwgAccessRevokedError,
    AwgDeviceLimitError,
    AwgError,
    AwgPeer,
    DeviceLabelError,
    DevicePlatform,
    IssuedConfig,
    add_device,
    device_limit,
    get_awg_client,
    is_platform,
    issue_device_config,
    normalize_device_label,
    peers_by_name,
    remove_device,
    rename_device,
    restore_access,
)
from includes.config_hide import hide_now, schedule_hide, track_config
from includes.memory_media import memory_media
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from state_machines.vpn import ViewVpnSubscription
from utils import L10nFormat, current_member, escape_mdv2, format_traffic

logger: FilteringBoundLogger = structlog.get_logger("awg-dialog")

# Время последнего подключения показываем по Москве - как и всё расписание бота.
_DISPLAY_TZ = ZoneInfo("Europe/Moscow")

# Платформы на экране выбора: телефоны строкой, компьютеры строкой.
PLATFORM_ROWS: tuple[tuple[DevicePlatform, ...], ...] = (("android", "ios"), ("windows", "macos", "linux"))

# Ключи dialog_data
_DEVICE = "awg_device"  # номер открытого устройства
_NAME_TARGET = "awg_name_target"  # None - новое устройство, число - переименование
_NAME_ERROR = "awg_name_error"  # готовый текст ошибки под вопросом о названии
_NEW_LABEL = "awg_new_label"  # название нового устройства, пока человек выбирает платформу
_PLATFORM_TARGET = "awg_platform_target"  # None - новое устройство, число - смена платформы
_CONFIG = "awg_config"  # memory://-ссылки на файл и QR открытого конфига
_SHOW_QR = "awg_show_qr"
_HIDDEN = "awg_hidden"  # токен конфига, который убрал таймер


# ========== Общие помощники ==========
def awg_allowed(access: AwgAccess | None) -> bool:
    """Окно AmneziaWG: у мембера нет разрешения (заведётся само) или оно не отозвано админом.

    ``suspended`` тоже пускает: выключенные ключи оживают по кнопке «Включить ключи».
    """
    return settings.awg.ENABLED and (access is None or access.status != "revoked")


async def _load_access(session: AsyncSession, telegram_id: int) -> tuple[Person, AwgAccess | None] | None:
    """Человек и его разрешение - или ``None``, если AmneziaWG ему сейчас закрыт.

    Разрешение ``None`` - мембер ещё не заводил устройств: окно пускает его, а строку заводит
    ``_grant_access`` при добавлении первого устройства. Здесь только чтение - геттеры не пишут в БД.
    """
    person = await get_person_with_member(session, telegram_id)
    if current_member(person) is None:
        return None
    access = await get_access_by_person(session, person.id)
    if not awg_allowed(access):
        return None
    return person, access


async def _grant_access(session: AsyncSession, person: Person, access: AwgAccess | None) -> AwgAccess:
    """Разрешение мембера, заведённое при необходимости. Коммит - на вызывающем хэндлере."""
    if access is not None:
        return access
    access = await create_access(session, person_id=person.id)
    await logger.ainfo("awg-access-auto-granted", person_id=person.id)
    return access


def _devices(access: AwgAccess | None) -> list[AwgDevice]:
    return list(access.devices) if access is not None else []


def _find_device(access: AwgAccess | None, number: int | None) -> AwgDevice | None:
    return next((device for device in _devices(access) if device.number == number), None)


def _device_name(l10n: FluentLocalization, device: AwgDevice) -> str:
    return device.label or l10n.format_value("vpn-awg-device-default-name-part", args={"number": device.number})


def _platform_name(l10n: FluentLocalization, platform: str | None) -> str:
    return l10n.format_value(f"vpn-awg-platform-{platform if is_platform(platform) else 'none'}-part")


def _device_status(l10n: FluentLocalization, peer: AwgPeer | None, peers_known: bool) -> str:
    if not peers_known:
        return l10n.format_value("vpn-awg-status-unknown-part")
    if peer is None:
        return l10n.format_value("vpn-awg-status-missing-part")
    return l10n.format_value(f"vpn-awg-status-{peer.connection_status()}-part")


def _format_last_online(l10n: FluentLocalization, moment: datetime | None) -> str:
    if moment is None:
        return l10n.format_value("vpn-awg-handshake-never-part")
    return moment.astimezone(_DISPLAY_TZ).strftime("%d.%m.%Y %H:%M")


def _format_traffic(l10n: FluentLocalization, peer: AwgPeer | None) -> str:
    """«скачано / отправлено» глазами человека - счётчики 3x-ui и так считают со стороны клиента."""
    if peer is None:
        return l10n.format_value("vpn-awg-no-data-part")
    return l10n.format_value(
        "vpn-awg-traffic-part",
        args={"down": format_traffic(peer.down), "up": format_traffic(peer.up)},
    )


def _middleware(dialog_manager: DialogManager) -> tuple[FluentLocalization, FilteringBoundLogger]:
    # В хэндлерах, в отличие от геттера, middleware-данные аргументами не приходят.
    return dialog_manager.middleware_data[L10N_FORMAT_KEY], dialog_manager.middleware_data[LOGGING_KEY]


def _awg_error_text(l10n: FluentLocalization, exc: Exception, access: AwgAccess | None) -> str:
    # IntegrityError - строка уже есть (например, устройство завели из CLI или второй копией бота):
    # человеку - обычная ошибка «попробуйте ещё». Свои апдейты человека Dispatcher сериализует (run.py).
    if isinstance(exc, AwgDeviceLimitError) and access is not None:
        return l10n.format_value(
            "vpn-awg-limit-alert", args={"used": len(access.devices), "limit": device_limit(access)}
        )
    if isinstance(exc, AwgAccessRevokedError):
        return l10n.format_value("vpn-awg-denied-alert")
    return l10n.format_value("vpn-awg-error-alert")


async def _delete_quietly(bot: Bot, chat_id: int, message_id: int) -> None:
    try:
        await bot.delete_message(chat_id, message_id)
    except TelegramAPIError as exc:
        await logger.awarning("awg-message-delete-failed", chat_id=chat_id, error=str(exc))


# ========== Конфиг: показ из памяти и автоскрытие ==========
def _forget_config(dialog_manager: DialogManager) -> str | None:
    """Убрать конфиг из окна. Возвращает его токен - сообщения с ключом скрывает ``config_hide``."""
    dialog_manager.dialog_data.pop(_SHOW_QR, None)
    config = dialog_manager.dialog_data.pop(_CONFIG, None)
    return config["token"] if config is not None else None


async def _open_config(dialog_manager: DialogManager, device: AwgDevice, name: str, config: IssuedConfig) -> None:
    """Показать конфиг окном (файл и QR - из памяти, без лишних сообщений) и завести таймер скрытия."""
    bot: Bot = dialog_manager.middleware_data["bot"]
    previous = _forget_config(dialog_manager)
    if previous is not None:
        # Окно открывают повторно: прежний конфиг убираем сразу, а не по его таймеру.
        await hide_now(bot, previous)

    token = uuid4().hex
    file_name = f"{settings.awg.TUNNEL_NAME}-{device.number}.conf"
    file_url = memory_media.put(config.text.encode(), file_name, owner=token)
    qr_url = None
    qr_apps: tuple[int, int] | None = None  # (вошло, всего) - если список исключений в QR урезан
    if config.qr is None:
        # Даже без исключений не влез (длинные I1-I5) - файла достаточно.
        await logger.awarning("awg-qr-too-big", number=device.number)
    else:
        qr_url = memory_media.put(config.qr.png, "amneziawg-qr.png", owner=token)
        if config.qr.truncated:
            qr_apps = (config.qr.included, config.qr.total)

    dialog_manager.dialog_data[_CONFIG] = {
        "token": token,
        "file": file_url,
        "qr": qr_url,
        "qr_apps": qr_apps,
        "name": name,
    }
    dialog_manager.dialog_data[_SHOW_QR] = False

    # Запись - до показа окна: менеджер сообщений учтёт уже первое сообщение с файлом.
    stack_id = dialog_manager.current_stack().id
    user = dialog_manager.middleware_data["event_from_user"]
    chat = dialog_manager.middleware_data["event_chat"]
    await track_config(token, user_id=user.id, chat_id=chat.id, stack_id=stack_id)

    # Привязка к стеку, а не к окну: если человек к тому времени закрыл диалог, перерисовка
    # не упадёт с UnknownIntent (а его хэндлер сбросил бы человеку меню).
    bg = dialog_manager.bg(stack_id=stack_id)

    async def refresh() -> None:
        # Сообщения уже удалены - окно конфига по токену поймёт, что показать «конфиг скрыт».
        await bg.update({_HIDDEN: token})

    schedule_hide(bot, token, settings.awg.CONFIG_TTL_SECONDS, refresh)

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


def _denied(l10n: FluentLocalization) -> dict[str, Any]:
    return _DENIED | {"text": l10n.format_value("vpn-awg-denied")}


async def get_awg_data(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    **kwargs,
) -> dict[str, Any]:
    async with async_session() as session:
        loaded = await _load_access(session, dialog_manager.event.from_user.id)

    if loaded is None:
        return _denied(l10n)
    person, access = loaded
    devices = _devices(access)

    peers: dict[str, AwgPeer] = {}
    peers_known = True
    if access is not None and devices:
        try:
            peers = await peers_by_name(get_awg_client(), access)
        except AwgError as exc:
            await log.aerror("vpn-awg-status-failed", person_id=person.id, error=str(exc))
            peers_known = False

    lines = [
        l10n.format_value(
            "vpn-awg-device-line-part",
            args={
                "name": _device_name(l10n, device),
                "status": _device_status(l10n, peers.get(device.client_name), peers_known),
            },
        )
        for device in devices
    ] or [l10n.format_value("vpn-awg-devices-empty-part")]

    limit = device_limit(access)
    text = l10n.format_value(
        "vpn-awg-devices",
        args={"used": len(devices), "limit": limit, "devices": escape_mdv2("\n".join(lines))},
    )
    is_suspended = access is not None and access.status == "suspended"
    if is_suspended:
        text += "\n\n" + l10n.format_value("vpn-awg-suspended-hint")
    if not peers_known:
        text += "\n\n" + l10n.format_value("vpn-awg-panel-error-hint")

    return _DENIED | {
        "is_allowed": True,
        "can_add": len(devices) < limit,
        "is_suspended": is_suspended,
        "devices": [(_device_name(l10n, device), device.number) for device in devices],
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
    device = _find_device(loaded[1] if loaded else None, dialog_manager.dialog_data.get(_DEVICE))

    if loaded is None or device is None:
        return _denied(l10n)

    peer: AwgPeer | None = None
    panel_ok = True
    try:
        peer = await get_awg_client().find_peer(device.client_name)
    except AwgError as exc:
        await log.aerror("vpn-awg-stats-failed", person_id=loaded[0].id, number=device.number, error=str(exc))
        panel_ok = False

    no_data = l10n.format_value("vpn-awg-no-data-part")
    text = l10n.format_value(
        "vpn-awg-device-card",
        args={
            "name": escape_mdv2(_device_name(l10n, device)),
            "platform": escape_mdv2(_platform_name(l10n, device.platform)),
            "status": escape_mdv2(_device_status(l10n, peer, panel_ok)),
            "online": escape_mdv2(_format_last_online(l10n, peer.last_online_at) if peer else no_data),
            "traffic": escape_mdv2(_format_traffic(l10n, peer)),
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
        device = _find_device(loaded[1] if loaded else None, target)
        name = _device_name(l10n, device) if device else ""
        text = l10n.format_value("vpn-awg-name-rename", args={"name": escape_mdv2(name), "max": MAX_DEVICE_LABEL_LEN})

    error = dialog_manager.dialog_data.get(_NAME_ERROR)
    if error:
        text += "\n\n" + escape_mdv2(error)
    return {"text": text}


async def get_platform_data(l10n: FluentLocalization, **kwargs) -> dict[str, Any]:
    mobile, desktop = PLATFORM_ROWS
    return {
        "text": l10n.format_value("vpn-awg-platform-question"),
        "mobile_platforms": [(_platform_name(l10n, platform), platform) for platform in mobile],
        "desktop_platforms": [(_platform_name(l10n, platform), platform) for platform in desktop],
    }


async def get_config_data(dialog_manager: DialogManager, l10n: FluentLocalization, **kwargs) -> dict[str, Any]:
    config = dialog_manager.dialog_data.get(_CONFIG)
    # Сработал таймер (или бот перезапускался и файла в памяти уже нет): окно без медиа -
    # aiogram-dialog удалит сообщение с файлом и пришлёт текст.
    if config is not None and (
        dialog_manager.dialog_data.get(_HIDDEN) == config["token"] or not memory_media.has(config["file"])
    ):
        _forget_config(dialog_manager)
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
        url=config["qr"] if show_qr else config["file"],
    )
    args = {"name": escape_mdv2(config["name"]), "minutes": max(1, settings.awg.CONFIG_TTL_SECONDS // 60)}
    text = l10n.format_value("vpn-awg-qr-caption" if show_qr else "vpn-awg-config-caption", args=args)
    if show_qr and config.get("qr_apps"):
        included, total = config["qr_apps"]
        text += "\n\n" + l10n.format_value("vpn-awg-qr-truncated", args={"included": included, "total": total})
    return {
        "show_media": True,
        "media": media,
        "has_qr": config["qr"] is not None,
        "show_qr": show_qr,
        "text": text,
    }


async def get_delete_data(dialog_manager: DialogManager, l10n: FluentLocalization, **kwargs) -> dict[str, Any]:
    async with async_session() as session:
        loaded = await _load_access(session, dialog_manager.event.from_user.id)
    device = _find_device(loaded[1] if loaded else None, dialog_manager.dialog_data.get(_DEVICE))
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
        await clb.answer(l10n.format_value("vpn-awg-denied-alert"), show_alert=True)
        return
    # Лимит проверяем до вопроса о названии, чтобы человек не печатал его зря.
    access = loaded[1]
    if len(_devices(access)) >= device_limit(access):
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
                await clb.answer(l10n.format_value("vpn-awg-denied-alert"), show_alert=True)
                return
            if loaded[1] is not None and loaded[1].status == "suspended":
                await restore_access(session, get_awg_client(), loaded[1])
                await session.commit()
    except (AwgError, IntegrityError) as exc:
        await log.aerror("vpn-awg-restore-failed", telegram_id=clb.from_user.id, error=str(exc))
        await clb.answer(l10n.format_value("vpn-awg-error-alert"), show_alert=True)
        return

    await clb.answer(l10n.format_value("vpn-awg-restored-alert"))


# ========== Хэндлеры: карточка устройства ==========
async def on_get_config(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    l10n, log = _middleware(dialog_manager)
    number = dialog_manager.dialog_data.get(_DEVICE)
    access: AwgAccess | None = None

    try:
        async with async_session() as session:
            loaded = await _load_access(session, clb.from_user.id)
            person, access = loaded or (None, None)
            device = _find_device(access, number)
            if person is None or access is None or device is None:
                await clb.answer(l10n.format_value("vpn-awg-denied-alert"), show_alert=True)
                return

            config = await issue_device_config(session, get_awg_client(), access, device, person)
            await session.commit()
    except (AwgError, IntegrityError) as exc:
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
            if loaded is None:
                # Доступ закрыли, пока человек подтверждал: ничего не удалено - так и говорим.
                await clb.answer(l10n.format_value("vpn-awg-denied-alert"), show_alert=True)
                await dialog_manager.switch_to(ViewVpnSubscription.AWG)
                return
            access = loaded[1]
            device = _find_device(access, number)
            # Устройство могли уже удалить из другого окна - удалять нечего, просто возвращаемся.
            if access is not None and device is not None:
                await remove_device(session, get_awg_client(), access, device)
                await session.commit()
    except (AwgError, IntegrityError) as exc:
        await log.aerror("vpn-awg-delete-failed", telegram_id=clb.from_user.id, number=number, error=str(exc))
        await clb.answer(l10n.format_value("vpn-awg-error-alert"), show_alert=True)
        await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)
        return

    dialog_manager.dialog_data.pop(_DEVICE, None)
    await clb.answer(l10n.format_value("vpn-awg-deleted-alert"))
    await dialog_manager.switch_to(ViewVpnSubscription.AWG)


# ========== Хэндлеры: название ==========
async def on_name_entered(
    message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, label: str
) -> None:
    # Сообщение с названием убираем, чтобы окно диалога осталось последним и редактировалось на месте.
    await _delete_quietly(message.bot, message.chat.id, message.message_id)
    dialog_manager.show_mode = ShowMode.EDIT

    target = dialog_manager.dialog_data.get(_NAME_TARGET)
    # Переименование - только подпись в нашей БД (панель не трогаем, уникальности нет): ошибок панели
    # и гонок за строку здесь не бывает, сбой самой БД пусть идёт в общий обработчик ошибок.
    async with async_session() as session:
        loaded = await _load_access(session, message.from_user.id)
        if loaded is None:
            await dialog_manager.switch_to(ViewVpnSubscription.AWG)
            return
        device = _find_device(loaded[1], target) if target is not None else None
        if device is not None:
            await rename_device(session, device, label)
            await session.commit()

    dialog_manager.dialog_data.pop(_NAME_ERROR, None)
    dialog_manager.dialog_data.pop(_NAME_TARGET, None)
    if target is not None:
        await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)
        return

    # Новое устройство заводим после выбора платформы: от неё зависит уже первый конфиг.
    dialog_manager.dialog_data[_NEW_LABEL] = label
    dialog_manager.dialog_data[_PLATFORM_TARGET] = None
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_PLATFORM)


async def on_name_error(message: Message, widget: ManagedTextInput, dialog_manager: DialogManager, error: ValueError):
    l10n, _ = _middleware(dialog_manager)
    await _delete_quietly(message.bot, message.chat.id, message.message_id)
    dialog_manager.show_mode = ShowMode.EDIT
    problem = error.problem if isinstance(error, DeviceLabelError) else "empty"
    dialog_manager.dialog_data[_NAME_ERROR] = l10n.format_value(
        f"vpn-awg-name-{problem}-part", args={"max": MAX_DEVICE_LABEL_LEN}
    )


async def on_name_back(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data.pop(_NAME_ERROR, None)
    target = dialog_manager.dialog_data.pop(_NAME_TARGET, None)
    state = ViewVpnSubscription.AWG if target is None else ViewVpnSubscription.AWG_DEVICE
    await dialog_manager.switch_to(state)


# ========== Хэндлеры: платформа ==========
async def on_start_platform(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data[_PLATFORM_TARGET] = dialog_manager.dialog_data.get(_DEVICE)
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_PLATFORM)


async def on_platform_selected(
    clb: CallbackQuery, widget: Select, dialog_manager: DialogManager, platform: str
) -> None:
    l10n, log = _middleware(dialog_manager)
    if not is_platform(platform):
        await clb.answer()
        return
    target = dialog_manager.dialog_data.get(_PLATFORM_TARGET)
    access: AwgAccess | None = None

    try:
        async with async_session() as session:
            loaded = await _load_access(session, clb.from_user.id)
            if loaded is None:
                await clb.answer(l10n.format_value("vpn-awg-denied-alert"), show_alert=True)
                await dialog_manager.switch_to(ViewVpnSubscription.AWG)
                return
            person, access = loaded

            if target is None:
                label = dialog_manager.dialog_data.get(_NEW_LABEL)
                access = await _grant_access(session, person, access)
                device, config = await add_device(session, get_awg_client(), access, person, label, platform)
                await session.commit()
            else:
                device = _find_device(access, target)
                if device is not None:
                    await set_device_platform(session, device, platform)
                    await session.commit()
                config = None
    except (AwgError, IntegrityError) as exc:
        await log.aerror("vpn-awg-platform-failed", telegram_id=clb.from_user.id, target=target, error=str(exc))
        await clb.answer(_awg_error_text(l10n, exc, access), show_alert=True)
        return

    dialog_manager.dialog_data.pop(_PLATFORM_TARGET, None)
    if config is None:
        await clb.answer(l10n.format_value("vpn-awg-platform-changed-alert"), show_alert=True)
        await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)
        return

    dialog_manager.dialog_data.pop(_NEW_LABEL, None)
    dialog_manager.dialog_data[_DEVICE] = device.number
    await clb.answer()
    await _open_config(dialog_manager, device, _device_name(l10n, device), config)


async def on_platform_back(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    target = dialog_manager.dialog_data.pop(_PLATFORM_TARGET, None)
    if target is not None:
        await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE)
        return
    # Новое устройство: возвращаемся к названию, оно ещё нигде не сохранено.
    dialog_manager.dialog_data.pop(_NEW_LABEL, None)
    dialog_manager.dialog_data[_NAME_TARGET] = None
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_NAME)


# ========== Хэндлеры: конфиг ==========
async def on_toggle_qr(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    dialog_manager.dialog_data[_SHOW_QR] = not dialog_manager.dialog_data.get(_SHOW_QR, False)


async def on_config_message(message: Message, widget: MessageInput, dialog_manager: DialogManager) -> None:
    # Без этого aiogram-dialog перерисовал бы окно новым сообщением под репликой - ещё одна копия ключа.
    dialog_manager.show_mode = ShowMode.NO_UPDATE


async def on_config_done(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager) -> None:
    token = _forget_config(dialog_manager)
    if token is not None:
        await hide_now(clb.bot, token)
    # Сообщение с файлом уже удалено - карточку шлём новым сообщением.
    await dialog_manager.switch_to(ViewVpnSubscription.AWG_DEVICE, show_mode=ShowMode.DELETE_AND_SEND)


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
        Group(
            Select(
                Format("{item[0]}"),
                id="awg_devices",
                item_id_getter=lambda item: item[1],
                items="devices",
                on_click=on_select_device,
            ),
            width=2,
        ),
        Button(
            L10nFormat("vpn-awg-add-btn"),
            id="awg_add",
            on_click=on_start_add,
            when=F["is_allowed"] & F["can_add"],
        ),
        # Конфиг 3.1 старые клиенты не импортируют или молча не подключаются - даём ссылки на свежие.
        Row(
            Url(L10nFormat("vpn-awg-wgtunnel-btn"), L10nFormat("vpn-awg-wgtunnel-url")),
            Url(L10nFormat("vpn-awg-android-btn"), L10nFormat("vpn-awg-android-url")),
            Url(L10nFormat("vpn-awg-ios-btn"), L10nFormat("vpn-awg-ios-url")),
            when="is_allowed",
        ),
        SwitchTo(L10nFormat("back-btn"), id="awg_back", state=ViewVpnSubscription.VIEW),
        getter=get_awg_data,
        state=ViewVpnSubscription.AWG,
    ),
    # --- Карточка устройства ---
    Window(
        Format("{text}"),
        Button(L10nFormat("vpn-awg-get-config-btn"), id="awg_get_config", on_click=on_get_config, when="has_device"),
        Row(
            Button(L10nFormat("vpn-awg-rename-btn"), id="awg_rename", on_click=on_start_rename),
            Button(L10nFormat("vpn-awg-platform-btn"), id="awg_platform", on_click=on_start_platform),
            SwitchTo(L10nFormat("vpn-awg-delete-btn"), id="awg_delete", state=ViewVpnSubscription.AWG_DELETE),
            when="has_device",
        ),
        SwitchTo(L10nFormat("back-btn"), id="awg_device_back", state=ViewVpnSubscription.AWG),
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
        Button(L10nFormat("back-btn"), id="awg_name_back", on_click=on_name_back),
        getter=get_name_data,
        state=ViewVpnSubscription.AWG_NAME,
    ),
    # --- Платформа ---
    Window(
        Format("{text}"),
        Row(
            Select(
                Format("{item[0]}"),
                id="awg_platforms_mobile",
                item_id_getter=lambda item: item[1],
                items="mobile_platforms",
                on_click=on_platform_selected,
            ),
        ),
        Row(
            Select(
                Format("{item[0]}"),
                id="awg_platforms_desktop",
                item_id_getter=lambda item: item[1],
                items="desktop_platforms",
                on_click=on_platform_selected,
            ),
        ),
        Button(L10nFormat("back-btn"), id="awg_platform_back", on_click=on_platform_back),
        getter=get_platform_data,
        state=ViewVpnSubscription.AWG_PLATFORM,
    ),
    # --- Конфиг: файл или QR в одном сообщении с кнопками ---
    Window(
        DynamicMedia("media", when="show_media"),
        Format("{text}"),
        Row(
            Button(
                L10nFormat("vpn-awg-show-qr-btn"),
                id="awg_show_qr",
                on_click=on_toggle_qr,
                when=F["has_qr"] & ~F["show_qr"],
            ),
            Button(L10nFormat("vpn-awg-show-file-btn"), id="awg_show_file", on_click=on_toggle_qr, when="show_qr"),
            Button(L10nFormat("vpn-awg-done-btn"), id="awg_config_done", on_click=on_config_done),
        ),
        MessageInput(on_config_message, content_types=ContentType.ANY),
        getter=get_config_data,
        state=ViewVpnSubscription.AWG_CONFIG,
    ),
    # --- Подтверждение удаления ---
    Window(
        Format("{text}"),
        Row(
            Button(L10nFormat("vpn-awg-delete-yes-btn"), id="awg_delete_yes", on_click=on_delete_confirmed),
            SwitchTo(L10nFormat("back-btn"), id="awg_delete_back", state=ViewVpnSubscription.AWG_DEVICE),
        ),
        getter=get_delete_data,
        state=ViewVpnSubscription.AWG_DELETE,
    ),
)
