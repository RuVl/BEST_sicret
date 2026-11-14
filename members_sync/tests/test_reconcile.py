from datetime import date
from types import SimpleNamespace

from sync.reconcile import match_identity_changes, removal_block_reason

BIRTHDAY = date(2001, 3, 14)
ALL_SHEETS = {"A": 61, "B": 260, "B-ex": 253}


def _member(key: str, name: str | None = "Петрова Анна Игоревна", birthday: date | None = BIRTHDAY):
    return SimpleNamespace(identity_key=key, full_name_ru=name, full_name_en=None, birthday=birthday)


def test_fixed_email_moves_the_row_to_the_new_key():
    changes = match_identity_changes([_member("petrova@best-eu.org")], [_member("petrva@best-eu.org")])

    assert changes.renames == {"petrva@best-eu.org": "petrova@best-eu.org"}
    assert changes.unresolved == []


def test_name_is_compared_like_the_identity_key():
    new = [_member("new@best-eu.org", "семёнов  иван")]
    old = [_member("old@best-eu.org", "Семенов Иван")]

    assert match_identity_changes(new, old).renames == {"old@best-eu.org": "new@best-eu.org"}


def test_added_email_moves_the_row_keyed_by_name():
    new = [_member("orlova@best-eu.org", "Орлова Мария")]
    old = [_member("орлова мария", "Орлова Мария")]

    assert match_identity_changes(new, old).renames == {"орлова мария": "orlova@best-eu.org"}


def test_other_person_is_not_touched():
    changes = match_identity_changes([_member("new@best-eu.org", "Новиков Пётр")], [_member("old@best-eu.org")])

    assert changes.renames == {}
    assert changes.unresolved == []


def test_namesake_with_other_birthday_is_left_for_a_human():
    changes = match_identity_changes(
        [_member("new@best-eu.org", birthday=date(2001, 1, 1))],
        [_member("old@best-eu.org")],
    )

    assert changes.renames == {}
    assert changes.unresolved == ["Петрова Анна Игоревна"]


def test_missing_birthday_is_not_proof_of_the_same_person():
    changes = match_identity_changes(
        [_member("new@best-eu.org", birthday=None)],
        [_member("old@best-eu.org", birthday=None)],
    )

    assert changes.renames == {}
    assert changes.unresolved == ["Петрова Анна Игоревна"]


def test_several_candidates_are_left_for_a_human():
    changes = match_identity_changes(
        [_member("new@best-eu.org")],
        [_member("old1@best-eu.org"), _member("old2@best-eu.org")],
    )

    assert changes.renames == {}
    assert changes.unresolved == ["Петрова Анна Игоревна"]


def test_single_deleted_rows_are_applied():
    assert removal_block_reason(ALL_SHEETS, vanished_count=1, max_removed=10) is None
    assert removal_block_reason(ALL_SHEETS, vanished_count=10, max_removed=10) is None


def test_mass_removal_blocks_the_run():
    assert "11" in removal_block_reason(ALL_SHEETS, vanished_count=11, max_removed=10)


def test_raised_limit_lets_a_real_cleanup_through():
    assert removal_block_reason(ALL_SHEETS, vanished_count=50, max_removed=100) is None


def test_unread_sheet_blocks_even_a_small_removal():
    reason = removal_block_reason({"A": 61, "B": 260}, vanished_count=1, max_removed=10)

    assert "Ex-members" in reason


def test_empty_sheet_counts_as_unread():
    reason = removal_block_reason({"A": 0, "B": 260, "B-ex": 253}, vanished_count=1, max_removed=10)

    assert "Database of Members" in reason


def test_nothing_vanished_means_nothing_to_block():
    assert removal_block_reason({}, vanished_count=0, max_removed=10) is None
