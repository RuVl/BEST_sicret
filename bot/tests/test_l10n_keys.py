"""Fluent молча возвращает имя ключа, если шаблон не распарсился.

Ловушек две: пустая строка обрывает многострочное сообщение, а строка, начинающаяся
с ``*``, читается как синтаксис вариантов. Поэтому ключи новых экранов проверяем явно.

Вторая проверка - экранирование: текст сообщения уходит с ``parse_mode=MarkdownV2``,
а подписи кнопок и алерты - обычным текстом, где экранирование видно как есть.
"""

import re

import pytest

from includes import get_fluent_localization

# Значения подставляем уже экранированными - ровно так их отдают геттеры и джоб.
ARGS = {
    "name": "Иванов Иван",
    "category": "Борда",
    "roles": "VP4HR of X Board",
    "local_involvement": "l",
    "international_involvement": "i",
    "best_events": "b",
    "url": r"https://vpn\.example\.org/sub/abc",
    "traffic": r"1\.20 ГБ",
    "revoked": 1,
    "failed": 0,
    "details": r"ivan@best\-eu\.org",
}

PROFILE_KEYS = [
    "profile-card",
    "profile-not-member",
    "profile-vpn-btn",
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


# Уходят в сообщение с MarkdownV2 - спецсимволы обязаны быть экранированы.
MESSAGE_KEYS = [
    "profile-card",
    "profile-not-member",
    "vpn-none",
    "vpn-active",
    "vpn-disabled",
    "vpn-orphaned",
    "vpn-revoked-notice",
    "vpn-revoke-report",
]

# Подписи кнопок и текст алертов Telegram показывает как есть, разметки там нет.
PLAIN_KEYS = [
    "profile-vpn-btn",
    "vpn-issue-btn",
    "vpn-refresh-btn",
    "vpn-handbook-btn",
    "vpn-handbook-url",
    "vpn-issued",
    "vpn-error",
    "vpn-access-denied",
]

# Внутри кода и URL ссылки MarkdownV2 точку экранировать не требует - вырезаем такие куски.
_CODE_OR_LINK = re.compile(r"`[^`]*`|\((?:https?|tg)://[^)]*\)")
_UNESCAPED_SPECIAL = re.compile(r"(?<!\\)[.!]")


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


@pytest.mark.parametrize("key", MESSAGE_KEYS)
def test_message_keys_are_escaped_for_markdown_v2(l10n, key):
    rendered = _CODE_OR_LINK.sub("", l10n.format_value(key, args=ARGS))

    assert not _UNESCAPED_SPECIAL.search(rendered)


@pytest.mark.parametrize("key", PLAIN_KEYS)
def test_plain_keys_have_no_escapes(l10n, key):
    assert "\\" not in l10n.format_value(key, args=ARGS)


def test_profile_card_keeps_all_sections(l10n):
    rendered = l10n.format_value("profile-card", args=ARGS)

    assert "Роли" in rendered
    assert "Мероприятия BEST" in rendered
