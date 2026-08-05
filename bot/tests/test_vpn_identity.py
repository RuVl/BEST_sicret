from includes.vpn.identity import (
    belongs_to_person,
    build_client_email,
    fallback_client_email,
    is_valid_client_id,
)


class TestIsValidClientId:
    def test_plain_email_is_valid(self):
        assert is_valid_client_id("ivan.ivanov@best-eu.org")

    def test_empty_is_invalid(self):
        assert not is_valid_client_id("")

    def test_space_is_invalid(self):
        assert not is_valid_client_id("ivan ivanov@best-eu.org")

    def test_slashes_are_invalid(self):
        assert not is_valid_client_id("a/b")
        assert not is_valid_client_id(r"a\b")

    def test_control_char_is_invalid(self):
        assert not is_valid_client_id("mail\n@best-eu.org")


class TestBuildClientEmail:
    def test_uses_best_email(self):
        assert build_client_email(7, "ivan@best-eu.org") == "ivan@best-eu.org"

    def test_strips_surrounding_spaces(self):
        assert build_client_email(7, "  ivan@best-eu.org  ") == "ivan@best-eu.org"

    def test_falls_back_when_email_is_missing(self):
        assert build_client_email(7, None) == "lbg-7"
        assert build_client_email(7, "   ") == "lbg-7"

    def test_falls_back_when_email_is_rejected_by_panel_rules(self):
        assert build_client_email(7, "ivan ivanov@best-eu.org") == "lbg-7"

    def test_fallback_format(self):
        assert fallback_client_email(42) == "lbg-42"


class TestBelongsToPerson:
    NAMES = ("Иванов Иван Иванович", "Ivan Ivanov")

    def _check(self, tg_id: int, comment: str) -> bool:
        return belongs_to_person(
            client_tg_id=tg_id,
            client_comment=comment,
            telegram_id=123456789,
            full_names=self.NAMES,
        )

    def test_full_match(self):
        assert self._check(123456789, "Иванов Иван Иванович")

    def test_matches_any_of_known_names(self):
        assert self._check(123456789, "Ivan Ivanov")

    def test_ignores_case_yo_and_extra_spaces(self):
        assert belongs_to_person(
            client_tg_id=123456789,
            client_comment="  пётр   ПЕТРОВ ",
            telegram_id=123456789,
            full_names=("Пётр Петров",),
        )

    def test_empty_panel_fields_are_not_a_conflict(self):
        # Админ завёл клиента по почте, но не заполнил tgId/comment - это всё равно наш человек.
        assert self._check(0, "")

    def test_foreign_tg_id_rejected(self):
        assert not self._check(987654321, "Иванов Иван Иванович")

    def test_foreign_name_rejected(self):
        assert not self._check(123456789, "Сидоров Пётр")
