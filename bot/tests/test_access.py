"""Предикат доступа: кто считается состоящим в LBG.

Модели инстанцируются без сессии - предикат чистый и в БД не ходит.
"""

from datetime import UTC, datetime

from database.models import LbgMember, Person
from utils import current_member


def _person(member: LbgMember | None) -> Person:
    person = Person(telegram_id=1, full_name="Иванов Иван")
    person.lbg_member = member
    return person


def _member(**kwargs) -> LbgMember:
    defaults = {"identity_key": "ivan@best-eu.org", "is_active": False, "is_excluded": False}
    return LbgMember(**(defaults | kwargs))


class TestCurrentMember:
    def test_active_member_allowed(self):
        member = _member(membership_category="board", is_active=True)

        assert current_member(_person(member)) is member

    def test_alumni_allowed(self):
        # Главная причина правки: alumni не активен, но из группы не выбывал.
        member = _member(membership_category="alumni")

        assert current_member(_person(member)) is member

    def test_excluded_denied(self):
        member = _member(membership_category="ex_member", is_excluded=True)

        assert current_member(_person(member)) is None

    def test_removed_from_sheet_denied(self):
        member = _member(membership_category="alumni", removed_from_sheet_at=datetime.now(UTC))

        assert current_member(_person(member)) is None

    def test_unlinked_person_denied(self):
        assert current_member(_person(None)) is None

    def test_unknown_person_denied(self):
        assert current_member(None) is None
