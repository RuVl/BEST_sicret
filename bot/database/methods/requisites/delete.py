from sqlalchemy.ext.asyncio import AsyncSession

from database.models.requisites import Requisites


async def delete_requisites(
    session: AsyncSession,
    requisites: Requisites,
) -> None:
    """
    Удаляет реквизиты из базы данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        requisites: Объект Requisites для удаления
    """
    await session.delete(requisites)
    await session.flush()
