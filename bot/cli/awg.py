"""Админское управление AmneziaWG: отозвать доступ, вернуть его или поменять лимит устройств.

Запуск внутри контейнера бота (обёртки - ``make awg-list`` / ``awg-grant`` / ``awg-revoke``)::

    python3 -m cli.awg list
    python3 -m cli.awg grant @username [--devices 3] [--no-notify]
    python3 -m cli.awg revoke @username [--delete]

Человек указывается Telegram-username'ом (``@ivan``) или числовым Telegram ID и должен хоть раз
нажать /start в боте. Активным мемберам AmneziaWG открыт и без ``grant``: разрешение заводится
само с первым устройством. ``grant`` нужен, чтобы вернуть отозванный доступ или
выставить личный лимит устройств; ключи в 3x-ui появятся, когда человек сам заведёт устройства в боте.

``grant`` и ``revoke`` сначала печатают, на кого и что именно сделают, и спрашивают ``[y/n]``.

"""

import argparse
import asyncio
import sys

from cli.common import CliError, confirm, describe_person, find_person, run, send_bot
from database.main import async_session
from database.methods.awg_access import (
    create_access,
    get_access_by_person,
    list_accesses,
    mark_revoked,
    set_device_limit,
)
from database.models import AwgAccess
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
from includes.notify import notify
from utils.access import current_member


def _devices(access: AwgAccess) -> str:
    return f"устройств {len(access.devices)}/{device_limit(access)}"


async def _send_granted_notice(telegram_id: int, limit: int) -> bool:
    text = get_fluent_localization().format_value("vpn-awg-granted-notice", args={"limit": limit})
    async with send_bot() as bot:
        return await notify(bot, telegram_id, text)


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
        print(f"{access.status:<9}  {member:<9}  {_devices(access):<14}  {describe_person(person)}  [{names}]")


async def cmd_grant(args: argparse.Namespace) -> None:
    if args.devices is not None and args.devices < 1:
        raise CliError("--devices: нужно хотя бы одно устройство")

    async with async_session() as session:
        person = await find_person(session, args.who)
        who = describe_person(person)
        if current_member(person) is None:
            raise CliError(f"{who} не состоит в LBG - бот всё равно не покажет ему VPN")

        access = await get_access_by_person(session, person.id)
        opens = access is None or access.status == "revoked"
        if not opens and args.devices is None:
            print(f"У {who} уже есть доступ ({access.status}, {_devices(access)})")
            return

        plan = [f"Кому: {who}"]
        if access is None:
            plan.append("Открыть AmneziaWG")
        elif opens:
            plan.append(f"Вернуть доступ и включить ключей в панели: {len(access.devices)}")
        if args.devices is not None:
            plan.append(f"Лимит устройств: {device_limit(access)} -> {args.devices}")
        # Пишем человеку только о появившемся доступе: смена лимита в боте для него ничего не меняет.
        notify_person = args.notify and opens
        if notify_person:
            plan.append("Написать человеку в Telegram, что доступ открыт")

        if not confirm("\n".join(plan)):
            print("Отменено")
            return

        if access is None:
            access = await create_access(session, person_id=person.id, device_limit=args.devices)
            action = "выдан"
        elif access.status == "revoked":
            # Выключенные при отзыве ключи включаем все сразу - человеку не нужно перезапрашивать конфиги.
            await restore_access(session, get_awg_client(), access)
            if args.devices is not None:
                await set_device_limit(session, access, args.devices)
            action = "возвращён"
        else:
            await set_device_limit(session, access, args.devices)
            action = "обновлён"

        await session.commit()
        print(f"Доступ {action}: {who}, {_devices(access)}")
        if len(access.devices) > device_limit(access):
            # Лишние ключи не удаляем молча: человек сам решит, какое устройство убрать.
            print("Внимание: устройств больше лимита - новые завести нельзя, пока лишние не удалят.")
        telegram_id = person.telegram_id
        limit = device_limit(access)

    if notify_person:
        if await _send_granted_notice(telegram_id, limit):
            print("Уведомление отправлено.")
        else:
            print("Уведомление не дошло (человек мог заблокировать бота) - подробности в логе бота.")


async def cmd_revoke(args: argparse.Namespace) -> None:
    async with async_session() as session:
        person = await find_person(session, args.who)
        who = describe_person(person)
        access = await get_access_by_person(session, person.id)
        if access is None:
            raise CliError(f"У {who} нет доступа к AmneziaWG")

        devices = len(access.devices)
        if args.delete:
            plan = f"Удалить устройств вместе с ключами в панели безвозвратно: {devices}"
        else:
            plan = f"Выключить ключей в панели: {devices} (вернутся при повторном grant)"
        if not confirm(f"Кому: {who}\nОтозвать доступ к AmneziaWG\n{plan}"):
            print("Отменено")
            return

        client = get_awg_client()
        # Сначала панель, потом БД: если панель недоступна, разрешение остаётся как было.
        if args.delete:
            removed = await remove_peers(session, client, access)
            print(f"Удалено устройств вместе с ключами: {removed}")
        else:
            found = await disable_peers(client, access)
            print(f"Выключено ключей в панели: {found} (вернутся при повторном grant)")

        await mark_revoked(session, access)
        await session.commit()
        print(f"Доступ отозван: {who}")


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

    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    if not settings.awg.ENABLED:
        print("AWG_INBOUND_ID не задан - AmneziaWG в боте выключен.", file=sys.stderr)
        return 2
    return asyncio.run(run(args.handler(args), expected=(AwgError,)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
