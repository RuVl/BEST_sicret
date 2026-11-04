"""SQL-двойник ``utils.access.current_member``: тот же предикат членства, но в запросе.

Меняя правило «состоит в LBG», меняйте обе стороны - иначе меню бота и ночные джобы разойдутся
(джоб отзовёт доступ тому, кому меню его ещё показывает, или наоборот).
"""

from best_db.models import LbgMember, Person
from sqlalchemy import ColumnElement, or_


def left_lbg() -> ColumnElement[bool]:
    """Человек больше не в LBG: привязку сняли, участника исключили или он пропал из таблицы.

    Запрос должен делать ``outerjoin(LbgMember, Person.lbg_member_id == LbgMember.id)``.
    """
    return or_(
        Person.lbg_member_id.is_(None),
        LbgMember.is_excluded.is_(True),
        LbgMember.removed_from_sheet_at.is_not(None),
    )
