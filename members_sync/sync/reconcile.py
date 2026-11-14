"""Сверка прогона с базой: что стало со строками, ключей которых больше нет в таблице.

Уход из группы виден отдельно: человека переносят на лист Ex-members, ключ остаётся прежним. Пропажа ключа со всех
листов значит другое: строку удалили (доступы должны закрыться), сменился email (это тот же человек) или таблицу
прочитали неверно (трогать базу нельзя). Здесь чистые решения, какой это случай: запросы - в ``database/methods``.
"""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from typing import Protocol

from parsing.normalizers import normalize_identity_name

# Без любого из этих листов пропажа строк говорит о сломанном чтении, а не об удалении людей.
EXPECTED_LAYOUTS: dict[str, str] = {
    "A": "Database of Members",
    "B": "Alumni+Former+abroad+guests+inactive",
    "B-ex": "Ex-members",
}

# Заметка-тревога о неприменённом прогоне: первая ячейка первого листа.
ALERT_CELL = "A1"


class MemberIdentity(Protocol):
    """Общее у строки таблицы (``ParsedMember``) и строки базы (``LbgMember``)."""

    identity_key: str
    full_name_ru: str | None
    full_name_en: str | None
    birthday: date | None


@dataclass
class IdentityChanges:
    """``renames``: старый ключ -> новый. ``unresolved``: похоже на смену email, но без уверенности."""

    renames: dict[str, str] = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)


def _group_by_name[T: MemberIdentity](members: Iterable[T]) -> dict[str, list[T]]:
    groups: dict[str, list[T]] = defaultdict(list)
    for member in members:
        name = normalize_identity_name(member.full_name_ru or member.full_name_en)
        if name:
            groups[name].append(member)
    return groups


def match_identity_changes(new: Iterable[MemberIdentity], vanished: Iterable[MemberIdentity]) -> IdentityChanges:
    """Сопоставить новые ключи с пропавшими по ФИО и дате рождения.

    Ошибка здесь отдаст чужую привязку и доступы, поэтому переносим только единственную пару с совпавшей и
    заполненной датой рождения. Остальное возвращаем в ``unresolved``: такие случаи разбирает человек.
    """
    changes = IdentityChanges()
    vanished_by_name = _group_by_name(vanished)

    for name, new_members in _group_by_name(new).items():
        old_members = vanished_by_name.get(name)
        if not old_members:
            continue

        new_member, old_member = new_members[0], old_members[0]
        is_single_pair = len(new_members) == 1 and len(old_members) == 1
        if is_single_pair and new_member.birthday and new_member.birthday == old_member.birthday:
            changes.renames[old_member.identity_key] = new_member.identity_key
        else:
            changes.unresolved.append(new_member.full_name_ru or new_member.full_name_en or name)

    return changes


def removal_block_reason(records_by_layout: dict[str, int], vanished_count: int, max_removed: int) -> str | None:
    """Причина не применять прогон, если таблица выглядит прочитанной неверно, иначе ``None``.

    Удаление отдельных строк сюда не попадает: оно применяется и закрывает доступы. Если пропала большая часть
    таблицы, ночные джобы отключили бы VPN всем этим людям из-за переименованного листа или сдвинутой колонки.
    """
    if not vanished_count:
        return None

    empty = [title for layout, title in EXPECTED_LAYOUTS.items() if not records_by_layout.get(layout)]
    if empty:
        return f"не прочитаны листы: {', '.join(empty)}; пропало бы строк: {vanished_count}"

    if vanished_count > max_removed:
        return f"за один прогон пропало строк: {vanished_count}, а допустимо MAX_REMOVED_PER_RUN={max_removed}"

    return None


def removal_alert(reason: str) -> str:
    """Текст заметки для людей, которые открыли таблицу: что сломалось и как это снять."""
    return (
        "ВАЖНО: синхронизация участников остановлена, база не обновляется. "
        "Пока это так, удалённые и перенесённые на Ex-members не теряют доступы.\n"
        f"Причина: {reason}.\n"
        "Как снять: верните лист или строки. Если таблицу чистили намеренно, "
        "поднимите MAX_REMOVED_PER_RUN на один прогон. Заметка исчезнет сама после успешного прогона."
    )
