"""Имя клиента AmneziaWG - его email в панели 3x-ui.

Имя глобально уникально в панели, а одно устройство - отдельный клиент (в одном инбаунде у email
ровно один ключ). Имя ``awg-<номер>-<email человека>``: префикс ``awg-`` отличает такие клиенты
от VLESS-подписок в общем списке панели, а email тот же, что у VLESS-клиента человека, - в админке
сразу видно, чьё устройство. Символы проверяем по правилам панели (``includes.vpn.identity``).
"""

from collections.abc import Iterable

from database.models import AwgDevice
from includes.vpn.identity import build_client_email, fallback_client_email, is_valid_client_id

MAX_CLIENT_NAME_LEN: int = AwgDevice.__table__.c.client_name.type.length
CLIENT_NAME_PREFIX = "awg-"
MAX_DEVICE_LABEL_LEN = 32


def is_valid_client_name(value: str) -> bool:
    return len(value) <= MAX_CLIENT_NAME_LEN and is_valid_client_id(value)


def fallback_device_client_name(person_id: int, number: int) -> str:
    """Имя без почты: у человека нет пригодного email или такое имя уже заняло чужое устройство."""
    return f"{CLIENT_NAME_PREFIX}{number}-{fallback_client_email(person_id)}"


def device_client_name(person_id: int, best_email: str | None, number: int) -> str:
    """Имя устройства по email человека и номеру устройства.

    Имя фиксируется в БД, когда бот заводит клиента в панели: смена почты потом его не меняет,
    иначе бот потерял бы уже выданный ключ. Без пригодного email - ``lbg-<person_id>``, как у VLESS.
    """
    name = f"{CLIENT_NAME_PREFIX}{number}-{build_client_email(person_id, best_email)}"
    if is_valid_client_name(name):
        return name
    return fallback_device_client_name(person_id, number)


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
