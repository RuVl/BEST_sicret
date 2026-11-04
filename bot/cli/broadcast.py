"""Рассылка произвольного сообщения из файла (обёртка - ``make broadcast``)::

    python3 -m cli.broadcast /tmp/broadcast.txt --group all
    python3 -m cli.broadcast /tmp/broadcast.txt --group awg,board --to @ivan,123456789

Текст - MarkdownV2 как есть. Получатели - объединение групп (``AUDIENCES``) и поимённо указанных
людей без повторов. Без ``--group`` и ``--to`` команда ничего не шлёт: «всем» - только явным
``--group all``. Перед отправкой печатает текст и список получателей и спрашивает ``[y/n]``.
"""

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path

from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest, TelegramRetryAfter
from best_db.models import Person
from sqlalchemy.ext.asyncio import AsyncSession

from cli.common import CliError, confirm, describe_person, run, send_bot
from database.main import async_session
from database.methods.person import (
    find_person_by_handle,
    list_active_member_persons,
    list_all_persons,
    list_awg_persons,
    list_board_persons,
    list_vless_persons,
)
from utils import parse_person_handle

# Группы получателей вычисляются из данных, без ручной разметки. Новая группа - запрос
# в ``database/methods/person/list.py`` и строка здесь.
AUDIENCES: dict[str, Callable[[AsyncSession], Awaitable[list[Person]]]] = {
    "all": list_all_persons,
    "members": list_active_member_persons,
    "board": list_board_persons,
    "awg": list_awg_persons,
    "vless": list_vless_persons,
}

# Telegram режет рассылку больше ~30 сообщений в секунду - идём с запасом.
SEND_INTERVAL = 0.1

USAGE = (
    "Кому отправить? Укажите группы и/или людей:\n"
    "  make broadcast file=msg.txt group=all\n"
    "  make broadcast file=msg.txt group=awg,board\n"
    "  make broadcast file=msg.txt to=@ivan,123456789\n"
    f"Группы: {', '.join(AUDIENCES)}"
)

# Ошибки самого текста: на следующем получателе они повторятся, слать дальше бессмысленно.
_TEXT_ERRORS = ("can't parse entities", "message is too long", "message text is empty")


# === Разбор аргументов ===


def _split(raw: str | None) -> list[str]:
    """``"a, b,,a"`` -> ``["a", "b"]``: пустые элементы и повторы отбрасываем, порядок сохраняем."""
    items = (item.strip() for item in (raw or "").split(","))
    return list(dict.fromkeys(item for item in items if item))


def parse_groups(raw: str | None, available: Iterable[str]) -> list[str]:
    """Имена групп из ``group=``; неизвестная - ошибка со списком доступных."""
    names = list(available)
    groups = _split((raw or "").lower())
    unknown = [name for name in groups if name not in names]
    if unknown:
        raise CliError(f"Неизвестная группа: {', '.join(unknown)}. Доступные: {', '.join(names)}")
    return groups


def parse_handles(raw: str | None) -> list[int | str]:
    """``to=@ivan,123`` -> ``["ivan", 123]``; то, что не похоже на ник или ID, - ошибка до отправки."""
    items = _split(raw)
    handles = [parse_person_handle(item) for item in items]
    bad = [item for item, handle in zip(items, handles, strict=True) if handle is None]
    if bad:
        raise CliError(f"Не похоже на @username или Telegram ID: {', '.join(bad)}")
    return list(dict.fromkeys(handle for handle in handles if handle is not None))


def unique_recipients(persons: Iterable[Person]) -> list[Person]:
    """Без повторов по Telegram ID: человек из нескольких групп получит сообщение один раз."""
    unique: dict[int, Person] = {}
    for person in persons:
        unique.setdefault(person.telegram_id, person)
    return list(unique.values())


def read_text(path: Path) -> str:
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise CliError(f"Не удалось прочитать {path}: {exc}") from exc
    if not text:
        raise CliError(f"{path}: пустой файл")
    return text


# === Отправка ===


@dataclass
class BroadcastResult:
    total: int
    sent: int = 0
    # Кому не дошло - и после остановки тоже: туда же попадают все, до кого очередь не дошла.
    failed: list[int] = field(default_factory=list)
    # Почему Telegram не принял сам текст (разметка, длина): рассылка остановлена.
    stopped: str | None = None


def is_text_error(exc: TelegramBadRequest) -> bool:
    return any(marker in exc.message.lower() for marker in _TEXT_ERRORS)


async def _send(bot: Bot, chat_id: int, text: str) -> None:
    try:
        await bot.send_message(chat_id, text)
    except TelegramRetryAfter as exc:
        # Telegram сам сказал, сколько ждать, - ждём и повторяем один раз, а не теряем получателя.
        await asyncio.sleep(exc.retry_after)
        await bot.send_message(chat_id, text)


async def send_all(bot: Bot, recipients: list[Person], text: str) -> BroadcastResult:
    """Разослать по одному с паузой; недошедшие копим, ошибка самого текста останавливает рассылку."""
    result = BroadcastResult(total=len(recipients))
    for index, person in enumerate(recipients):
        if index:
            await asyncio.sleep(SEND_INTERVAL)
        try:
            await _send(bot, person.telegram_id, text)
        except TelegramBadRequest as exc:
            if is_text_error(exc):
                result.stopped = exc.message
                result.failed.extend(rest.telegram_id for rest in recipients[index:])
                return result
            result.failed.append(person.telegram_id)
            print(f"Не дошло: {describe_person(person)}: {exc.message}", file=sys.stderr)
        except TelegramAPIError as exc:
            # Заблокировал бота, удалил аккаунт и т.п. - остальным это не мешает.
            result.failed.append(person.telegram_id)
            print(f"Не дошло: {describe_person(person)}: {exc.message}", file=sys.stderr)
        else:
            result.sent += 1
    return result


# === Команда ===


async def _collect_recipients(groups: list[str], handles: list[int | str]) -> list[Person]:
    async with async_session() as session:
        persons: list[Person] = []
        for name in groups:
            persons.extend(await AUDIENCES[name](session))

        missing: list[str] = []
        for handle in handles:
            person = await find_person_by_handle(session, handle)
            if person is None:
                missing.append(f"@{handle}" if isinstance(handle, str) else str(handle))
            else:
                persons.append(person)
    if missing:
        raise CliError(f"Не найдены (должны хотя бы раз нажать /start в боте): {', '.join(missing)}")
    return unique_recipients(persons)


def _preview(text: str, recipients: list[Person]) -> str:
    people = "\n".join(f"  {describe_person(person)}" for person in recipients)
    return f"Текст сообщения:\n-----\n{text}\n-----\nПолучателей: {len(recipients)}\n{people}"


async def broadcast(args: argparse.Namespace) -> None:
    groups = parse_groups(args.group, AUDIENCES)
    handles = parse_handles(args.to)
    if not groups and not handles:
        raise CliError(USAGE)

    text = read_text(args.file)
    recipients = await _collect_recipients(groups, handles)
    if not recipients:
        print("Получателей нет - отправлять некому.")
        return

    if not confirm(_preview(text, recipients)):
        print("Отменено")
        return

    async with send_bot() as bot:
        result = await send_all(bot, recipients, text)

    print(f"Отправлено {result.sent} из {result.total}")
    if result.failed:
        print(f"Не дошло (для повтора - to=): {','.join(map(str, result.failed))}")
    if result.stopped is not None:
        raise CliError(f"Telegram не принял текст: {result.stopped}. Рассылка остановлена - исправьте файл.")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cli.broadcast", description="Рассылка сообщения из файла")
    parser.add_argument("file", type=Path, help="текст в MarkdownV2")
    parser.add_argument("--group", help=f"группы через запятую: {', '.join(AUDIENCES)}")
    parser.add_argument("--to", help="@username и Telegram ID через запятую")
    return parser


def main(argv: list[str]) -> int:
    args = _parser().parse_args(argv)
    return asyncio.run(run(broadcast(args)))


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
