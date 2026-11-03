"""Каркас админских CLI-команд (``make awg-*``, ``make broadcast``).

Общее для всех команд: человек указывается ``@username`` или Telegram ID, перед изменениями команда
показывает, что сделает, и спрашивает ``[y/n]``, а ожидаемые ошибки печатаются без трейсбэка.
"""

import sys
from collections.abc import AsyncIterator, Awaitable
from contextlib import asynccontextmanager

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession

from database.main import engine
from database.methods.person import find_person_by_handle
from database.models import Person
from env import settings
from includes.vpn import close_xui_client
from utils import parse_person_handle

CONFIRM_PROMPT = "Вы уверены [y/n]: "
_YES = {"y", "yes"}


class CliError(Exception):
    """Ошибка ввода или состояния - печатается без трейсбэка."""


def describe_person(person: Person) -> str:
    """``ФИО (tg 123)`` - ФИО из таблицы мемберов; без связи с мембером или без ФИО - просто ``tg 123``.

    ``lbg_member`` должен быть подгружен заранее: вне сессии ленивой подгрузки нет.
    """
    member = person.lbg_member
    name = (member.full_name_ru or "").strip() if member is not None else ""
    return f"{name} (tg {person.telegram_id})" if name else f"tg {person.telegram_id}"


def confirm(prompt: str) -> bool:
    """Показать, что команда сделает, и спросить согласия. Да - только ``y``/``yes``.

    Всё остальное, пустой ввод и запуск без терминала (``EOFError``) - отказ: меняющая команда
    не должна срабатывать «по умолчанию».
    """
    print(prompt)
    try:
        answer = input(CONFIRM_PROMPT)
    except (EOFError, KeyboardInterrupt):
        print()
        return False
    return answer.strip().lower() in _YES


async def find_person(session: AsyncSession, who: str) -> Person:
    """Person по ``@username`` или Telegram ID, сразу с членством."""
    handle = parse_person_handle(who)
    if handle is None:
        raise CliError(f"{who!r}: нужен @username или Telegram ID")
    person = await find_person_by_handle(session, handle)
    if person is None:
        raise CliError(f"{who}: человек не найден - он должен хотя бы раз нажать /start в боте")
    return person


@asynccontextmanager
async def send_bot() -> AsyncIterator[Bot]:
    """Бот только для отправки сообщений из CLI - без polling, сессию закрываем сами."""
    bot = Bot(token=settings.telegram.API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN_V2))
    try:
        yield bot
    finally:
        await bot.session.close()


async def run(command: Awaitable[None], *, expected: tuple[type[Exception], ...] = ()) -> int:
    """Выполнить команду и вернуть код выхода; ``CliError`` и ``expected`` - сообщением, без трейсбэка.

    Engine и клиент панели закрываем сами: иначе asyncio ругается на незакрытые соединения при выходе.
    """
    try:
        await command
    except (CliError, *expected) as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    finally:
        await close_xui_client()
        await engine.dispose()
    return 0
