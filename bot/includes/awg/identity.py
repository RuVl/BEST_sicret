"""Имя клиента AmneziaWG.

Установщик и панель пускают только ASCII-буквы, цифры, ``_`` и ``-``, не длиннее 15 символов
(``validate_client_name`` в amneziawg-web), а имя глобально уникально на интерфейсе.
"""

import re
from collections.abc import Iterable

MAX_CLIENT_NAME_LEN = 15
MAX_DEVICE_LABEL_LEN = 32

_CLIENT_NAME = re.compile(rf"[A-Za-z0-9_-]{{1,{MAX_CLIENT_NAME_LEN}}}")


def is_valid_client_name(value: str) -> bool:
    return _CLIENT_NAME.fullmatch(value) is not None


def device_client_name(person_id: int, number: int) -> str:
    """Стабильное имя по ``person_id`` и номеру устройства: не зависит от смены ФИО или username."""
    return f"lbg{person_id}-{number}"


def free_device_number(used: Iterable[int]) -> int:
    """Наименьший свободный номер: удалённое устройство освобождает свой номер."""
    taken = set(used)
    number = 1
    while number in taken:
        number += 1
    return number


def normalize_device_label(value: str) -> str:
    """Название устройства от человека: схлопываем пробелы и переносы, проверяем длину.

    ``ValueError`` - сигнал ``TextInput`` показать подсказку и спросить ещё раз.
    """
    label = " ".join(value.split())
    if not label:
        raise ValueError("пустое название")
    if len(label) > MAX_DEVICE_LABEL_LEN:
        raise ValueError(f"название длиннее {MAX_DEVICE_LABEL_LEN} символов")
    if any(not char.isprintable() for char in label):
        raise ValueError("непечатаемые символы")
    return label


def build_peer_comment(
    full_name: str,
    username: str | None,
    telegram_id: int,
    number: int,
    label: str | None = None,
) -> str:
    """Подпись пира в панели - чтобы в админке было видно, чей это ключ и на каком он устройстве."""
    handle = f"@{username}" if username else "без username"
    device = f"«{label}»" if label else f"устройство {number}"
    return f"{full_name} ({handle}, tg {telegram_id}), {device} - выдан ботом"
