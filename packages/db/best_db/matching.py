"""Сопоставление человека (Person) с участником (LbgMember) по Telegram-хэндлу.

Общий код для bot и members_sync. Обе службы держат свои engine/session, но
семантику «грязного» столбца ``lbg_members.telegram`` (хэндл как есть из Google
Sheets) описываем в одном месте, чтобы нормализация совпадала на обеих сторонах.
"""

import re

# Префиксы ссылок/подписей перед самим username: "https://t.me/", "telegram: ", "tg://resolve?domain=".
_PREFIX_RE = re.compile(
    r"^(?:https?://)?(?:www\.)?(?:t(?:elegram)?\.me/|telegram:\s*|tg://resolve\?domain=)",
    re.IGNORECASE,
)
# Telegram username: латиница/цифры/подчёркивание, 5–32 символа (ботов и старые короткие имена не различаем).
_USERNAME_RE = re.compile(r"[a-z0-9_]{5,32}")


def normalize_telegram_handle(value: str | None) -> str | None:
    """Грязный Telegram-хэндл → «голый» username в нижнем регистре или ``None``.

    Понимает ``@user``, ``user``, ``t.me/user``, ``https://t.me/user``, ``telegram: user``.
    Возвращает ``None``, когда username не извлекается: пустое значение, ссылка-приглашение
    (``t.me/+...``, ``t.me/joinchat/...``) или строка без валидного username.
    """
    if not value:
        return None

    handle = _PREFIX_RE.sub("", value.strip())
    handle = handle.lstrip("@")
    # Обрезать хвост: "user/", "user?start=...", "user (заметка)".
    handle = re.split(r"[\s/?#]", handle, maxsplit=1)[0].lower()

    match = _USERNAME_RE.fullmatch(handle)
    return match.group(0) if match else None
