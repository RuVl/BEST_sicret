from dialogs.user.vpn import _format_traffic


class TestFormatTraffic:
    def test_zero_is_megabytes(self):
        assert _format_traffic(0) == "0.0 МБ"

    def test_under_gigabyte_is_megabytes(self):
        assert _format_traffic(5 * 1024**2) == "5.0 МБ"

    def test_gigabyte_and_above(self):
        assert _format_traffic(3 * 1024**3) == "3.00 ГБ"

    def test_boundary_switches_to_gigabytes(self):
        assert _format_traffic(1024**3) == "1.00 ГБ"
