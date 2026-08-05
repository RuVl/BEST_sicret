"""Выбор идентификатора клиента в панели 3x-ui.

Панель запрещает в ``email`` и ``subId`` символы ``/``, ``\\``, пробелы и управляющие
(``hasForbiddenClientChar`` в исходниках панели), а сам ``email`` глобально уникален.
"""

import unicodedata
from collections.abc import Sequence

_FORBIDDEN = {"/", "\\"}


def is_valid_client_id(value: str) -> bool:
    """Проверка по тем же правилам, что и на стороне панели."""
    if not value:
        return False
    return not any(char in _FORBIDDEN or char.isspace() or unicodedata.category(char) == "Cc" for char in value)


def fallback_client_email(person_id: int) -> str:
    """Идентификатор для тех, у кого нет best-почты или чья почта уже занята."""
    return f"lbg-{person_id}"


def build_client_email(person_id: int, best_email: str | None) -> str:
    """Основной идентификатор: best-почта, иначе стабильный ``lbg-<person_id>``."""
    candidate = (best_email or "").strip()
    if candidate and is_valid_client_id(candidate):
        return candidate
    return fallback_client_email(person_id)


def _normalize_name(value: str) -> str:
    """ФИО для сравнения: регистр, «ё» и лишние пробелы значения не имеют."""
    return " ".join(value.replace("ё", "е").replace("Ё", "Е").casefold().split())


def belongs_to_person(
    *,
    client_tg_id: int,
    client_comment: str,
    telegram_id: int,
    full_names: Sequence[str],
) -> bool:
    """Принадлежит ли уже существующий клиент панели этому человеку.

    Совпадение по email вызывающая сторона установила до вызова, здесь проверяем остальное:
    клиента, заведённого руками с той же почтой, tg-id и ФИО, надо подхватить, а не плодить
    рядом второй ключ. Незаполненные ``tgId``/``comment`` (админ поленился) противоречием
    не считаем - чужие значения считаем.
    """
    if client_tg_id and client_tg_id != telegram_id:
        return False

    comment = client_comment.strip()
    if not comment:
        return True

    return any(_normalize_name(comment) == _normalize_name(name) for name in full_names if name)
