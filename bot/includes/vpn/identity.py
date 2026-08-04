"""Выбор идентификатора клиента в панели 3x-ui.

Панель запрещает в ``email`` и ``subId`` символы ``/``, ``\\``, пробелы и управляющие
(``hasForbiddenClientChar`` в исходниках панели), а сам ``email`` глобально уникален.
"""

import unicodedata

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
