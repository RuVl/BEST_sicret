"""Админская выдача AmneziaWG: кому из мемберов открыть запасной протокол.

Запуск внутри контейнера бота (обёртки - ``make awg-list`` / ``awg-grant`` / ``awg-revoke``)::

    python3 -m cli.awg list
    python3 -m cli.awg grant @username [--name ivan_pc] [--no-notify]
    python3 -m cli.awg revoke @username [--delete]

Человек указывается Telegram-username'ом (``@ivan``) или числовым Telegram ID и должен хоть раз
нажать /start в боте. ``grant`` только записывает разрешение: ключ в панели AmneziaWG появится,
когда человек сам запросит конфиг кнопкой - так бот не плодит ключи, которыми никто не пользуется.
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
    get_access_by_client_name,
    get_access_by_person,
    list_accesses,
    mark_granted,
    mark_revoked,
)
from database.models import Person
from env import settings
from includes import get_fluent_localization
from includes.awg import AwgError, close_awg_client, default_client_name, get_awg_client, is_valid_client_name
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


async def _send_granted_notice(telegram_id: int) -> None:
    bot = Bot(token=settings.telegram.API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
    try:
        await notify(bot, telegram_id, get_fluent_localization().format_value("vpn-awg-granted-notice"))
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
        issued = access.issued_at.strftime("%Y-%m-%d") if access.issued_at else "конфиг не запрашивал"
        print(f"{access.client_name:<15}  {access.status:<9}  {member:<9}  {issued:<20}  {_describe(person)}")


async def cmd_grant(args: argparse.Namespace) -> None:
    async with async_session() as session:
        person = await _find_person(session, args.who)
        if current_member(person) is None:
            raise CliError(f"{_describe(person)} не состоит в LBG - бот всё равно не покажет ему VPN")

        access = await get_access_by_person(session, person.id)
        if access is not None:
            if access.status != "revoked":
                print(f"У {_describe(person)} уже есть доступ: {access.client_name} ({access.status})")
                return
            await mark_granted(session, access)
            action = "возвращён"
        else:
            name = args.name or default_client_name(person.id)
            if not is_valid_client_name(name):
                raise CliError(f"{name}: имя клиента - латиница, цифры, _ и -, до 15 символов")
            if await get_access_by_client_name(session, name) is not None:
                raise CliError(f"{name}: имя клиента уже занято")
            access = await create_access(session, person_id=person.id, client_name=name)
            action = "выдан"

        await session.commit()
        print(f"Доступ {action}: {access.client_name} -> {_describe(person)}")
        telegram_id = person.telegram_id

    if args.notify:
        await _send_granted_notice(telegram_id)
        print("Уведомление отправлено.")


async def cmd_revoke(args: argparse.Namespace) -> None:
    client = get_awg_client()
    async with async_session() as session:
        person = await _find_person(session, args.who)
        access = await get_access_by_person(session, person.id)
        if access is None:
            raise CliError(f"У {_describe(person)} нет доступа к AmneziaWG")

        # Сначала панель, потом БД: если панель недоступна, разрешение остаётся как было.
        peer = await client.find_peer(access.client_name)
        if peer is None:
            print("Ключа в панели нет - конфиг не запрашивали или его удалили руками.")
        elif args.delete:
            await client.remove_peer(peer.id)
            print(f"Ключ {access.client_name} удалён из панели.")
        else:
            if not peer.disabled:
                await client.set_disabled(peer.id, True)
            print(f"Ключ {access.client_name} выключен в панели (вернётся при повторном grant).")

        await mark_revoked(session, access)
        await session.commit()
        print(f"Доступ отозван: {_describe(person)}")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.awg", description="Выдача доступа к AmneziaWG")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("list", help="все разрешения").set_defaults(handler=cmd_list)

    grant = commands.add_parser("grant", help="открыть AmneziaWG мемберу")
    grant.add_argument("who", help="@username или Telegram ID")
    grant.add_argument("--name", help="имя клиента в AmneziaWG (по умолчанию lbg<person_id>)")
    grant.add_argument("--no-notify", dest="notify", action="store_false", help="не писать человеку в Telegram")
    grant.set_defaults(handler=cmd_grant)

    revoke = commands.add_parser("revoke", help="забрать AmneziaWG")
    revoke.add_argument("who", help="@username или Telegram ID")
    revoke.add_argument("--delete", action="store_true", help="удалить ключ из панели, а не выключить")
    revoke.set_defaults(handler=cmd_revoke)

    return parser


async def _main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    if not settings.awg.ENABLED:
        print("AWG_WEB_BASE_URL / AWG_WEB_API_TOKEN не заданы - AmneziaWG в боте выключен.", file=sys.stderr)
        return 2

    try:
        await args.handler(args)
    except (CliError, AwgError) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_awg_client()
        await engine.dispose()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main(sys.argv[1:])))
