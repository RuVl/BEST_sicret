"""Разбор того, как админ указывает человека в CLI: ``@username`` или числовой Telegram ID."""

import re

# Ник Telegram не начинается с цифры, поэтому строка из одних цифр - всегда ID.
_ID_RE = re.compile(r"\d+")
_USERNAME_RE = re.compile(r"[A-Za-z][A-Za-z0-9_]{0,31}")


def parse_person_handle(value: str) -> int | str | None:
    """``@Ivan``/``ivan`` -> ``"ivan"``, ``"123"`` -> ``123``; пустое или не похожее на ник -> ``None``.

    Ник отдаём в нижнем регистре: Telegram его не различает, и уникальный индекс в БД - тоже.
    """
    value = value.strip()
    if _ID_RE.fullmatch(value):
        return int(value)
    username = value.removeprefix("@")
    return username.lower() if _USERNAME_RE.fullmatch(username) else None
