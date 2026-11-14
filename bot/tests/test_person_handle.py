"""Как админ указывает человека: ``@username`` или Telegram ID - разбор без БД."""

import pytest

from utils import parse_person_handle


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("@Ivan_Petrov", "ivan_petrov"),
        ("ivan_petrov", "ivan_petrov"),
        ("  @ivan  ", "ivan"),
        ("123456789", 123456789),
        (" 42 ", 42),
    ],
)
def test_parse_handle(raw: str, expected: int | str) -> None:
    assert parse_person_handle(raw) == expected


@pytest.mark.parametrize(
    "raw", ["", "   ", "@", "@@ivan", "-123", "@1ivan", "ivan petrov", "t.me/ivan", "@" + "a" * 33]
)
def test_parse_handle_rejects_garbage(raw: str) -> None:
    assert parse_person_handle(raw) is None
