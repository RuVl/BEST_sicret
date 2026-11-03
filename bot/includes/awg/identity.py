"""Имя клиента AmneziaWG - его email в панели 3x-ui.

Имя глобально уникально в панели, а одно устройство - отдельный клиент (в одном инбаунде у email
ровно один ключ). Имя ``awg-<номер>-<email человека>``: префикс ``awg-`` отличает такие клиенты
от VLESS-подписок в общем списке панели, а email тот же, что у VLESS-клиента человека, - в админке
сразу видно, чьё устройство. Символы проверяем по правилам панели (``includes.vpn.identity``).
"""

from collections.abc import Iterable
from typing import Literal

from database.models import AwgDevice
from includes.vpn.identity import build_client_email, fallback_client_email, is_valid_client_id

MAX_CLIENT_NAME_LEN: int = AwgDevice.__table__.c.client_name.type.length
CLIENT_NAME_PREFIX = "awg-"
MAX_DEVICE_LABEL_LEN: int = AwgDevice.__table__.c.label.type.length


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


# Невидимые символы, из которых складываются эмодзи (👨‍💻, флаги регионов): без них такие эмодзи
# распадаются. Остальные служебные символы (переносы, управляющие) в названии не нужны.
_EMOJI_JOINERS = frozenset({"\u200c", "\u200d"}) | frozenset(chr(code) for code in range(0xE0020, 0xE0080))

LabelProblem = Literal["empty", "too-long", "bad-chars"]


class DeviceLabelError(ValueError):
    """Название не подошло; ``problem`` выбирает текст подсказки человеку."""

    def __init__(self, problem: LabelProblem) -> None:
        super().__init__(problem)
        self.problem: LabelProblem = problem


def normalize_device_label(value: str) -> str:
    """Название устройства от человека: схлопываем пробелы и переносы, проверяем длину и символы.

    Длина - в кодовых точках, как её считает колонка БД: составной эмодзи занимает несколько.
    ``DeviceLabelError`` (``ValueError``) - сигнал ``TextInput`` показать подсказку и спросить ещё раз.
    """
    label = " ".join(value.split())
    if not label or all(char in _EMOJI_JOINERS for char in label.replace(" ", "")):
        raise DeviceLabelError("empty")
    if any(not char.isprintable() and char not in _EMOJI_JOINERS for char in label):
        raise DeviceLabelError("bad-chars")
    if len(label) > MAX_DEVICE_LABEL_LEN:
        raise DeviceLabelError("too-long")
    return label
