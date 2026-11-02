import pytest

from includes.awg import PLATFORMS, excluded_apps, is_platform, personalize_config
from includes.awg import platform as platform_module
from includes.awg.platform import EXCLUDED_APPS_FILE, parse_excluded_apps

# Конфиг, как его отдаёт панель: подпись клиента комментарием над [Peer].
CONF = """[Interface]
PrivateKey = 3333333333333333333333333333333333333333333=
Address = 10.70.0.2/32
MTU = 1393
DisableCookies = on

# BEST AWG ivan
[Peer]
PublicKey = 1111111111111111111111111111111111111111111=
Endpoint = 45.136.228.156:443
"""


class TestPersonalizeConfig:
    def test_name_is_first_line_for_every_platform(self):
        # WG Tunnel берёт имя туннеля из первого комментария файла, остальные клиенты его пропускают.
        for platform in (*PLATFORMS, None):
            assert personalize_config(CONF, platform, name="BEST VPN").startswith("# Name = BEST VPN\n[Interface]\n")

    def test_android_gets_excluded_apps_inside_interface(self):
        lines = personalize_config(CONF, "android", name="BEST VPN", excluded=("ru.a.b", "com.c.d")).splitlines()
        line = "ExcludedApplications = ru.a.b,com.c.d"
        assert lines.index(line) == lines.index("DisableCookies = on") + 1
        assert lines.index(line) < lines.index("[Peer]")

    @pytest.mark.parametrize("platform", ["ios", "windows", "macos", "linux", None])
    def test_other_platforms_never_get_excluded_apps(self, platform):
        # iOS/macOS и Windows отвергают конфиг с незнакомым ключом, awg-quick на Linux падает на нём.
        assert "ExcludedApplications" not in personalize_config(CONF, platform, name="", excluded=("ru.a.b",))

    def test_empty_name_adds_nothing(self):
        assert personalize_config(CONF, "ios", name="") == CONF


class TestExcludedApps:
    def test_parses_comments_blanks_and_duplicates(self):
        assert parse_excluded_apps("# Банки\nru.sberbankmobile\n\nru.sberbankmobile  # дубль\ncom.avito.android\n") == (
            "ru.sberbankmobile",
            "com.avito.android",
        )

    @pytest.mark.parametrize("line", ["not a package", "ru", "ru.a,ru.b", "ru.a\\nPostUp"])
    def test_rejects_garbage(self, line):
        # Мусор в строке сломал бы импорт конфига на телефоне.
        with pytest.raises(ValueError):
            parse_excluded_apps(line)

    def test_missing_file_means_no_exclusions(self, monkeypatch, tmp_path):
        # Без файла конфиг всё равно выдаётся - просто без списка, а не падает хэндлер.
        monkeypatch.setattr(platform_module, "EXCLUDED_APPS_FILE", tmp_path / "missing.txt")
        excluded_apps.cache_clear()
        try:
            assert excluded_apps() == ()
        finally:
            excluded_apps.cache_clear()

    def test_resource_file_is_valid(self):
        # Прямой разбор, без запасного пустого списка: битый файл должен ронять тест, а не прятаться.
        apps = parse_excluded_apps(EXCLUDED_APPS_FILE.read_text(encoding="utf-8"))
        assert "ru.sberbankmobile" in apps
        assert len(apps) == len(set(apps))


def test_platforms():
    assert is_platform("android")
    assert not is_platform("symbian")
    assert not is_platform(None)
