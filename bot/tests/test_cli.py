"""Каркас админских CLI: подтверждение ``[y/n]`` и описание человека - без БД и Telegram."""

import builtins

import pytest

from cli.common import CONFIRM_PROMPT, confirm, describe_person
from database.models import LbgMember, Person

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
