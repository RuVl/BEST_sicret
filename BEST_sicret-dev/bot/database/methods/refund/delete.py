from sqlalchemy.ext.asyncio import AsyncSession

from database.models.refund import Refund


async def delete_refund(
    session: AsyncSession,
    refund: Refund,
) -> None:
    """
    Удаляет возврат из базы данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        refund: Объект Refund для удаления
    """
    await session.delete(refund)
    await session.flush()





