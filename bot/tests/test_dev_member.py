"""``make dev-member``: кого признаёт ``current_member`` и когда команда отказывается - без БД."""

from datetime import UTC, datetime

import pytest
from best_db.matching import normalize_telegram_handle
from best_db.models import LbgMember, Person

from cli import dev_member as dev_member_cli
from cli.common import CliError
from cli.dev_member import DEFAULT_CATEGORY, grant_membership, main, new_member, parse_nick
from env import settings
from utils import current_member


@pytest.mark.parametrize(
    ("who", "nick"),
    [("@ivan_petrov", "ivan_petrov"), ("ivan_petrov", "ivan_petrov"), ("@Ivan_Petrov", "ivan_petrov")],
)
def test_parse_nick(who: str, nick: str) -> None:
    assert parse_nick(who) == nick


@pytest.mark.parametrize("who", ["", "@", "@abcd", "123456789", "@иван_петров", "t.me/+invite"])
def test_parse_nick_rejects_what_start_cannot_link(who: str) -> None:
    with pytest.raises(CliError):
        parse_nick(who)


def test_new_member_fills_every_required_column() -> None:
    member = new_member("ivan_petrov")
    missing = [
        column.name
        for column in LbgMember.__table__.columns
        if not column.nullable
        and not column.primary_key
        and column.default is None
        and column.server_default is None
        and getattr(member, column.key) is None
    ]
    assert missing == []


def test_new_member_is_found_by_start_lookup() -> None:
    assert normalize_telegram_handle(new_member("ivan_petrov").telegram) == "ivan_petrov"


@pytest.mark.parametrize(
    "state",
    [
        {"is_excluded": True, "membership_category": "ex_member"},
        {"removed_from_sheet_at": datetime(2026, 1, 1, tzinfo=UTC), "membership_category": "alumni"},
    ],
)
def test_former_member_passes_current_member_after_grant(state: dict) -> None:
    member = LbgMember(**state)
    person = Person(lbg_member=member)
    assert current_member(person) is None

    grant_membership(member)

    assert current_member(person) is member
    assert member.is_active is True


@pytest.mark.parametrize(
    ("before", "after"),
    [(None, DEFAULT_CATEGORY), ("ex_full_member", DEFAULT_CATEGORY), ("board", "board"), ("alumni", "alumni")],
)
def test_grant_keeps_real_category(before: str | None, after: str) -> None:
    member = LbgMember(membership_category=before)

    grant_membership(member)

    assert member.membership_category == after


def test_refuses_without_debug_before_touching_db(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def no_session():
        raise AssertionError("при DEBUG=False команда не должна открывать сессию")

    monkeypatch.setattr(settings.project, "DEBUG", False)
    monkeypatch.setattr(dev_member_cli, "async_session", no_session)

    assert main(["@ivan_petrov"]) == 1
    assert "DEBUG=False" in capsys.readouterr().err


def test_broken_db_gives_hint(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    def refused():
        raise ConnectionRefusedError

    monkeypatch.setattr(settings.project, "DEBUG", True)
    monkeypatch.setattr(dev_member_cli, "async_session", refused)

    assert main(["@ivan_petrov"]) == 1
    assert "make infra" in capsys.readouterr().err
