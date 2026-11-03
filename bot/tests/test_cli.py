"""Админские CLI: подтверждение ``[y/n]``, описание человека, разбор и отправка рассылки - без БД и Telegram."""

import argparse
import asyncio
import builtins

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.methods import SendMessage

from cli import broadcast as broadcast_cli
from cli.broadcast import broadcast, parse_groups, parse_handles, send_all, unique_recipients
from cli.common import CONFIRM_PROMPT, CliError, confirm, describe_person
from database.methods.person import AUDIENCES
from database.models import LbgMember, Person
from tests.fakes import FakeBot

# === confirm ===


def _answer(monkeypatch: pytest.MonkeyPatch, answer: str | type[BaseException]) -> list[str]:
    """Подменить ввод; вернуть список заданных вопросов."""
    asked: list[str] = []

    def fake_input(prompt: str = "") -> str:
        asked.append(prompt)
        if isinstance(answer, type):
            raise answer
        return answer

    monkeypatch.setattr(builtins, "input", fake_input)
    return asked


@pytest.mark.parametrize("answer", ["y", "yes", "Y", "YES", " y "])
def test_confirm_yes(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], answer: str) -> None:
    asked = _answer(monkeypatch, answer)

    assert confirm("Выключить ключей: 2") is True
    assert asked == [CONFIRM_PROMPT]
    assert "Выключить ключей: 2" in capsys.readouterr().out


@pytest.mark.parametrize("answer", ["n", "no", "", "  ", "да", "yy", "Yes please"])
def test_confirm_anything_else_is_no(monkeypatch: pytest.MonkeyPatch, answer: str) -> None:
    _answer(monkeypatch, answer)

    assert confirm("Удалить") is False


@pytest.mark.parametrize("error", [EOFError, KeyboardInterrupt])
def test_confirm_without_terminal_is_no(monkeypatch: pytest.MonkeyPatch, error: type[BaseException]) -> None:
    _answer(monkeypatch, error)

    assert confirm("Удалить") is False


def test_confirm_prompt_text() -> None:
    assert CONFIRM_PROMPT == "Вы уверены [y/n]: "


# === describe_person ===


def _person(full_name_ru: str | None = None, *, linked: bool = True) -> Person:
    person = Person(telegram_id=123456, full_name="Telegram Name", telegram_username="ivan")
    if linked:
        person.lbg_member = LbgMember(full_name_ru=full_name_ru)
    return person


def test_describe_with_member_name() -> None:
    assert describe_person(_person("Иванов Иван")) == "Иванов Иван (tg 123456)"


def test_describe_without_member() -> None:
    assert describe_person(_person(linked=False)) == "tg 123456"


@pytest.mark.parametrize("name", [None, "", "   "])
def test_describe_with_empty_member_name(name: str | None) -> None:
    assert describe_person(_person(name)) == "tg 123456"


# === broadcast: разбор group= / to= ===


def test_groups_union_without_duplicates() -> None:
    assert parse_groups("awg, board,,AWG ,", AUDIENCES) == ["awg", "board"]


def test_groups_empty() -> None:
    assert parse_groups(None, AUDIENCES) == []
    assert parse_groups(" , ", AUDIENCES) == []


def test_unknown_group_lists_available() -> None:
    with pytest.raises(CliError) as exc:
        parse_groups("awg,admins", AUDIENCES)

    message = str(exc.value)
    assert "admins" in message
    assert all(name in message for name in ("all", "members", "board", "awg", "vless"))


def test_handles_mixed_without_duplicates() -> None:
    assert parse_handles("@Ivan, 123,,ivan, 123 ,@petr") == ["ivan", 123, "petr"]


def test_handles_empty() -> None:
    assert parse_handles(None) == []
    assert parse_handles(",,") == []


def test_bad_handle_fails_before_sending() -> None:
    with pytest.raises(CliError, match="ivan petrov"):
        parse_handles("@ok_name,ivan petrov")


def test_recipients_unique_by_telegram_id() -> None:
    first, again, other = Person(telegram_id=1), Person(telegram_id=1), Person(telegram_id=2)

    assert unique_recipients([first, other, again]) == [first, other]


def test_no_group_and_no_to_sends_nothing() -> None:
    args = argparse.Namespace(group=None, to=" , ", file=None)

    with pytest.raises(CliError, match="group=all"):
        asyncio.run(broadcast(args))


# === broadcast: отправка ===


def _bad_request(message: str) -> TelegramBadRequest:
    return TelegramBadRequest(method=SendMessage(chat_id=0, text=""), message=message)


@pytest.fixture
def no_pause(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(broadcast_cli, "SEND_INTERVAL", 0)


@pytest.mark.usefixtures("no_pause")
def test_send_collects_failures_and_goes_on() -> None:
    bot = FakeBot(
        errors={
            2: TelegramForbiddenError(method=SendMessage(chat_id=2, text=""), message="bot was blocked by the user"),
            3: _bad_request("Bad Request: chat not found"),
        }
    )
    recipients = [Person(telegram_id=chat_id) for chat_id in (1, 2, 3, 4)]

    result = asyncio.run(send_all(bot, recipients, "Привет"))

    assert [chat_id for chat_id, _ in bot.sent] == [1, 4]
    assert (result.sent, result.total, result.failed, result.stopped) == (2, 4, [2, 3], None)


@pytest.mark.usefixtures("no_pause")
def test_markup_error_stops_broadcast() -> None:
    bot = FakeBot(errors={1: _bad_request("Bad Request: can't parse entities: Character '.' is reserved")})
    recipients = [Person(telegram_id=chat_id) for chat_id in (1, 2, 3)]

    result = asyncio.run(send_all(bot, recipients, "Привет."))

    assert bot.sent == []
    assert result.sent == 0
    assert result.failed == [1, 2, 3]
    assert result.stopped is not None and "can't parse entities" in result.stopped
