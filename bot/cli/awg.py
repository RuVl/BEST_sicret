"""Админское управление AmneziaWG: отозвать доступ, вернуть его или поменять лимит устройств.

Запуск внутри контейнера бота (обёртки - ``make awg-list`` / ``awg-grant`` / ``awg-revoke``)::

    python3 -m cli.awg list
    python3 -m cli.awg grant @username [--devices 3] [--no-notify]
    python3 -m cli.awg revoke @username [--delete]
    python3 -m cli.awg announce [--dry-run]

Человек указывается Telegram-username'ом (``@ivan``) или числовым Telegram ID и должен хоть раз
нажать /start в боте. Активным мемберам AmneziaWG открыт и без ``grant``: разрешение заводится
само при первом входе в окно. ``grant`` нужен, чтобы вернуть отозванный доступ или выставить личный
лимит устройств; ключи в 3x-ui появятся, когда человек сам заведёт устройства в боте.
"""

import argparse
import asyncio
import sys

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from database.main import async_session, engine
from database.methods.awg_access import (
    create_access,
    get_access_by_person,
    list_accesses,
    mark_revoked,
    set_device_limit,
)
from database.methods.person import list_active_member_persons
from database.models import AwgAccess, Person
from env import settings
from includes import get_fluent_localization
from includes.awg import (
    AwgError,
    device_limit,
    disable_peers,
    get_awg_client,
    remove_peers,
    restore_access,
)
from includes.vpn import close_xui_client
from jobs.revoke_vpn import notify
from utils.access import current_member


class CliError(Exception):
    """Ошибка ввода или состояния - печатается без трейсбэка."""


async def _find_person(session: AsyncSession, who: str) -> Person:
    """Person по ``@username`` или Telegram ID, сразу с членством."""
    query = select(Person).options(joinedload(Person.lbg_member))
    value = who.strip()
    if value.lstrip("-").isdigit():
        query = query.where(Person.telegram_id == int(value))
    else:
        query = query.where(func.lower(Person.telegram_username) == value.removeprefix("@").lower())

    person = await session.scalar(query)
    if person is None:
        raise CliError(f"{who}: человек не найден - он должен хотя бы раз нажать /start в боте")
    return person


def _describe(person: Person) -> str:
    handle = f"@{person.telegram_username}" if person.telegram_username else "без username"
    return f"{person.full_name} ({handle}, tg {person.telegram_id})"


def _devices(access: AwgAccess) -> str:
    return f"устройств {len(access.devices)}/{device_limit(access)}"


async def _send_granted_notice(telegram_id: int, limit: int) -> None:
    text = get_fluent_localization().format_value("vpn-awg-granted-notice", args={"limit": limit})
    bot = Bot(token=settings.telegram.API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
    try:
        await notify(bot, telegram_id, text)
    finally:
        await bot.session.close()


async def cmd_list(_: argparse.Namespace) -> None:
    async with async_session() as session:
        accesses = await list_accesses(session)

    if not accesses:
        print("Разрешений на AmneziaWG пока нет.")
        return

    for access in accesses:
        person = access.person
        member = "мембер" if current_member(person) else "НЕ мембер"
        names = ", ".join(device.client_name for device in access.devices) or "-"
        print(f"{access.status:<9}  {member:<9}  {_devices(access):<14}  {_describe(person)}  [{names}]")


async def cmd_grant(args: argparse.Namespace) -> None:
    if args.devices is not None and args.devices < 1:
        raise CliError("--devices: нужно хотя бы одно устройство")

    async with async_session() as session:
        person = await _find_person(session, args.who)
        if current_member(person) is None:
            raise CliError(f"{_describe(person)} не состоит в LBG - бот всё равно не покажет ему VPN")

        access = await get_access_by_person(session, person.id)
        if access is None:
            access = await create_access(session, person_id=person.id, device_limit=args.devices)
            action = "выдан"
        elif access.status == "revoked":
            # Выключенные при отзыве ключи включаем все сразу - человеку не нужно перезапрашивать конфиги.
            await restore_access(session, get_awg_client(), access)
            if args.devices is not None:
                await set_device_limit(session, access, args.devices)
            action = "возвращён"
        elif args.devices is not None:
            await set_device_limit(session, access, args.devices)
            action = "обновлён"
        else:
            print(f"У {_describe(person)} уже есть доступ ({access.status}, {_devices(access)})")
            return

        await session.commit()
        print(f"Доступ {action}: {_describe(person)}, {_devices(access)}")
        if len(access.devices) > device_limit(access):
            # Лишние ключи не удаляем молча: человек сам решит, какое устройство убрать.
            print("Внимание: устройств больше лимита - новые завести нельзя, пока лишние не удалят.")
        telegram_id = person.telegram_id
        limit = device_limit(access)
        notify_person = action != "обновлён"

    if args.notify and notify_person:
        await _send_granted_notice(telegram_id, limit)
        print("Уведомление отправлено.")


async def cmd_revoke(args: argparse.Namespace) -> None:
    client = get_awg_client()
    async with async_session() as session:
        person = await _find_person(session, args.who)
        access = await get_access_by_person(session, person.id)
        if access is None:
            raise CliError(f"У {_describe(person)} нет доступа к AmneziaWG")

        # Сначала панель, потом БД: если панель недоступна, разрешение остаётся как было.
        if args.delete:
            removed = await remove_peers(session, client, access)
            print(f"Удалено устройств вместе с ключами: {removed}")
        else:
            found = await disable_peers(client, access)
            print(f"Выключено ключей в панели: {found} (вернутся при повторном grant)")

        await mark_revoked(session, access)
        await session.commit()
        print(f"Доступ отозван: {_describe(person)}")


async def cmd_announce(args: argparse.Namespace) -> None:
    """Рассказать всем активным мемберам, что AmneziaWG теперь основной и старые конфиги надо получить заново."""
    async with async_session() as session:
        persons = [person for person in await list_active_member_persons(session) if current_member(person)]

    if args.dry_run:
        for person in persons:
            print(_describe(person))
        print(f"Получат сообщение: {len(persons)} (dry-run, ничего не отправлено)")
        return

    text = get_fluent_localization().format_value("vpn-awg-announce", args={"limit": settings.awg.DEVICE_LIMIT})
    bot = Bot(token=settings.telegram.API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
    try:
        for person in persons:
            await notify(bot, person.telegram_id, text)
            # Telegram режет рассылку больше ~30 сообщений в секунду - идём с запасом.
            await asyncio.sleep(0.1)
    finally:
        await bot.session.close()
    print(f"Отправлено: {len(persons)} (заблокировавшие бота пропущены, см. лог)")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.awg", description="Выдача доступа к AmneziaWG")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="все разрешения").set_defaults(handler=cmd_list)

    grant = commands.add_parser("grant", help="открыть AmneziaWG мемберу или сменить ему лимит устройств")
    grant.add_argument("who", help="@username или Telegram ID")
    grant.add_argument(
        "--devices",
        type=int,
        help=f"личный лимит устройств (по умолчанию AWG_DEVICE_LIMIT={settings.awg.DEVICE_LIMIT})",
    )
    grant.add_argument("--no-notify", dest="notify", action="store_false", help="не писать человеку в Telegram")
    grant.set_defaults(handler=cmd_grant)

    revoke = commands.add_parser("revoke", help="забрать AmneziaWG")
    revoke.add_argument("who", help="@username или Telegram ID")
    revoke.add_argument("--delete", action="store_true", help="удалить устройства и ключи, а не выключить")
    revoke.set_defaults(handler=cmd_revoke)

    announce = commands.add_parser("announce", help="разослать активным мемберам, что AmneziaWG - основной")
    announce.add_argument("--dry-run", action="store_true", help="только показать, кому уйдёт сообщение")
    announce.set_defaults(handler=cmd_announce)

    return parser


async def _main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    if not settings.awg.ENABLED:
        print("AWG_INBOUND_ID не задан - AmneziaWG в боте выключен.", file=sys.stderr)
        return 2

    try:
        await args.handler(args)
    except (CliError, AwgError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_xui_client()
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
