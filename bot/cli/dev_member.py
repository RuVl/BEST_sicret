"""Сделать человека участником LBG в локальной БД: меню бота открывается без доступа к Google-таблице.

Запуск на хосте, только при ``DEBUG=True`` (обёртка - ``make dev-member who=@ник``)::

    python -m cli.dev_member @username

Команду можно запускать повторно и до, и после /start. Подтверждения нет: она правит только локальную БД,
а настоящие данные участника (имя, контакты, категорию board) не трогает.
"""

import argparse
import asyncio
import sys

from best_db.matching import normalize_telegram_handle
from best_db.models import LbgMember
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from cli.common import CliError, run
from database.main import async_session
from database.methods.member import list_members_by_username
from database.methods.person import find_person_by_handle, release_lbg_members, set_lbg_member
from env import settings
from utils import parse_person_handle

DEFAULT_CATEGORY = "full_member"
_SOURCE = "make dev-member"


def require_debug() -> None:
    if not settings.project.DEBUG:
        raise CliError("Команда только для локальной разработки: при DEBUG=False она не запускается")


def parse_nick(who: str) -> str:
    """Ник в том виде, в каком его сравнивает /start. Ник короче 5 символов /start не свяжет - отказываем сразу."""
    handle = parse_person_handle(who)
    nick = normalize_telegram_handle(handle) if isinstance(handle, str) else None
    if nick is None:
        raise CliError(f"{who!r}: нужен ник Telegram, например @ivan_petrov (от 5 символов, не числовой ID)")
    return nick


def new_member(nick: str) -> LbgMember:
    """Участник с выдуманными данными. В ``identity_key`` - префикс, с которым не совпадёт строка из таблицы."""
    return LbgMember(
        identity_key=f"dev:{nick}",
        full_name_ru=f"Тестовый участник {nick}",
        telegram=nick,
        source_sheet=_SOURCE,
        raw={"source": _SOURCE},
    )


def grant_membership(member: LbgMember) -> None:
    """Выставить флаги так, чтобы ``current_member`` признал участника, в том числе бывшего."""
    member.is_active = True
    member.is_excluded = False
    member.removed_from_sheet_at = None
    if member.membership_category is None or member.membership_category.startswith("ex_"):
        member.membership_category = DEFAULT_CATEGORY


async def apply_dev_member(session: AsyncSession, nick: str) -> tuple[LbgMember, bool]:
    """Участник для ника и признак «создан». Коммит - на вызывающей стороне."""
    members = await list_members_by_username(session, nick)
    created = not members
    if created:
        members = [new_member(nick)]
        session.add_all(members)
        await session.flush()

    # Строк с одним ником в таблице может быть несколько: /start привязал бы любую из них.
    for member in members:
        grant_membership(member)
    member_ids = [member.id for member in members]
    await release_lbg_members(session, member_ids, nick)

    # /start привязывает только непривязанного, поэтому старую связь человека меняем здесь.
    person = await find_person_by_handle(session, nick)
    if person is not None and person.lbg_member_id not in member_ids:
        await set_lbg_member(session, person, members[0].id)
    return members[0], created


async def dev_member(who: str) -> None:
    require_debug()
    nick = parse_nick(who)
    try:
        async with async_session() as session:
            member, created = await apply_dev_member(session, nick)
            await session.commit()
    except (OSError, SQLAlchemyError) as exc:
        hint = "БД недоступна или без миграций. Выполните: make infra, затем make migrate"
        raise CliError(f"{hint} ({type(exc).__name__})") from exc

    action = "создан" if created else "обновлён"
    print(f"Участник @{nick} {action} (id {member.id}). Нажмите /start в боте с этого аккаунта.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.dev_member", description="Участник LBG для локальной разработки")
    parser.add_argument("who", help="ник Telegram: @username")
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    return asyncio.run(run(dev_member(args.who)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
