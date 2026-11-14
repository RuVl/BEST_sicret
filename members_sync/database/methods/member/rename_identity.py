from best_db.models import LbgMember
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession


async def rename_identity(session: AsyncSession, old_key: str, new_key: str) -> None:
    """Сменить ключ строки: ``id`` и привязка ``Person`` сохраняются, данные обновит следующий upsert."""
    await session.execute(update(LbgMember).where(LbgMember.identity_key == old_key).values(identity_key=new_key))
