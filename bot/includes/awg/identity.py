"""Имя клиента AmneziaWG - его email в панели 3x-ui.

Имя глобально уникально в панели. Правила - от прежнего сервера AmneziaWG (ASCII-буквы, цифры,
``_`` и ``-``, не длиннее 15 символов): с ними уже заведены устройства в БД, и они же проходят
проверку email в 3x-ui.
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


def build_peer_comment(full_name: str, username: str | None, telegram_id: int, number: int) -> str:
    """Подпись клиента в панели - чтобы в админке было видно, чей это ключ и какое устройство по счёту.

    Название устройства сюда не пишем: оно меняется в боте, а подпись в панели после создания
    бот не трогает (см. ``rename_device``).
    """
    handle = f"@{username}" if username else "без username"
    return f"{full_name} ({handle}, tg {telegram_id}), устройство {number} - выдан ботом"
