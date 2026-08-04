from includes.vpn.identity import build_client_email, fallback_client_email, is_valid_client_id


class TestIsValidClientId:
    def test_plain_email_is_valid(self):
        assert is_valid_client_id("ivan.ivanov@best-eu.org")

    def test_empty_is_invalid(self):
        assert not is_valid_client_id("")

    def test_space_is_invalid(self):
        assert not is_valid_client_id("ivan ivanov@best-eu.org")

    def test_slashes_are_invalid(self):
        assert not is_valid_client_id("a/b")
        assert not is_valid_client_id("a\\b")

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
