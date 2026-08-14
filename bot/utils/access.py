"""Единый предикат доступа: состоит ли человек в LBG.

Два флага ``LbgMember`` значат разное: ``is_active`` - может брать таски группы,
``is_excluded`` - исключён (лист Ex-members). Alumni и former не активны, но из группы
не выбывали, поэтому к ресурсам бота доступ у них остаётся.

Чистая функция без сессии и сети: ``lbg_member`` должен быть подгружен заранее
(``get_person_with_member``), иначе SQLAlchemy сходит в закрытую сессию.
"""

from database.models import LbgMember, Person


def current_member(person: Person | None) -> LbgMember | None:
    """Членство человека или ``None``, если он в группе не состоит."""
    member = person.lbg_member if person is not None else None
    if member is None or member.is_excluded or member.removed_from_sheet_at is not None:
        return None
    return member
