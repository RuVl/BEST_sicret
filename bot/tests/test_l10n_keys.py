"""Fluent молча возвращает имя ключа, если шаблон не распарсился.

Ловушек две: пустая строка обрывает многострочное сообщение, а строка, начинающаяся
с ``*``, читается как синтаксис вариантов. Поэтому ключи новых экранов проверяем явно.
"""

import pytest

from includes import get_fluent_localization

ARGS = {
    "name": "Иванов Иван",
    "category": "Борда",
    "status": "активный мембер",
    "roles": "VP4HR of X Board",
    "local_involvement": "l",
    "international_involvement": "i",
    "best_events": "b",
    "url": "https://vpn.example.org/sub/abc",
    "traffic": "1\\.20 ГБ",
    "revoked": 1,
    "failed": 0,
    "details": "ivan@best-eu.org",
}

PROFILE_KEYS = [
    "profile-card",
    "profile-active",
    "profile-inactive",
    "profile-not-member",
    "profile-vpn-btn",
    "close",
]

VPN_KEYS = [
    "vpn-none",
    "vpn-active",
    "vpn-disabled",
    "vpn-orphaned",
    "vpn-issued",
    "vpn-issue-btn",
    "vpn-refresh-btn",
    "vpn-handbook-btn",
    "vpn-handbook-url",
    "vpn-error",
    "vpn-access-denied",
    "vpn-revoked-notice",
    "vpn-revoke-report",
]


@pytest.fixture(scope="module")
def l10n():
    return get_fluent_localization()


@pytest.mark.parametrize("key", PROFILE_KEYS + VPN_KEYS)
def test_key_resolves(l10n, key):
    assert l10n.format_value(key, args=ARGS) != key


@pytest.mark.parametrize("key", ["profile-card", "vpn-active", "vpn-orphaned", "vpn-revoke-report"])
def test_multiline_message_is_not_truncated(l10n, key):
    """Обрыв шаблона проявляется как потеря хвоста, а не как ошибка."""
    assert "\n\n" in l10n.format_value(key, args=ARGS)


def test_profile_card_keeps_all_sections(l10n):
    rendered = l10n.format_value("profile-card", args=ARGS)

    assert "Роли" in rendered
    assert "Мероприятия BEST" in rendered
