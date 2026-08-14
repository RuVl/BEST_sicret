from collections.abc import Iterable
from datetime import datetime

from best_db.models import LbgMember
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


async def deactivate_missing(
    session: AsyncSession,
    seen_identity_keys: Iterable[str],
    now: datetime,
) -> int:
    """Пометить неактивными участников, которых не было в текущем прогоне.

    Данные не удаляются: ставится ``is_active=False`` и ``removed_from_sheet_at``.
    Затрагивает только тех, кто ещё считается присутствующим
    (``removed_from_sheet_at IS NULL``).

    ``is_excluded`` не трогаем: пропажа из таблицы и исключение из группы - разные
    события, второе видно только по листу Ex-members.
    """
    seen = set(seen_identity_keys)

    query = (
        update(LbgMember)
        .where(
            LbgMember.removed_from_sheet_at.is_(None),
            LbgMember.identity_key.notin_(seen) if seen else LbgMember.identity_key.isnot(None),
        )
        .values(
            is_active=False,
            removed_from_sheet_at=now,
            last_synced_at=now,
        )
    )
    result = await session.execute(query)
    return result.rowcount or 0
