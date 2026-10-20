"""Имя клиента AmneziaWG.

Установщик и панель пускают только ASCII-буквы, цифры, ``_`` и ``-``, не длиннее 15 символов
(``validate_client_name`` в amneziawg-web), а имя глобально уникально на интерфейсе.
"""

import re

MAX_CLIENT_NAME_LEN = 15

_CLIENT_NAME = re.compile(rf"[A-Za-z0-9_-]{{1,{MAX_CLIENT_NAME_LEN}}}")


def is_valid_client_name(value: str) -> bool:
    return _CLIENT_NAME.fullmatch(value) is not None


def default_client_name(person_id: int) -> str:
    """Стабильное имя по ``person_id``: не зависит от смены ФИО или username."""
    return f"lbg{person_id}"


def build_peer_comment(full_name: str, username: str | None, telegram_id: int) -> str:
    """Подпись пира в панели - чтобы в админке было видно, чей это ключ."""
    handle = f"@{username}" if username else "без username"
    return f"{full_name} ({handle}, tg {telegram_id}) - выдан ботом"
