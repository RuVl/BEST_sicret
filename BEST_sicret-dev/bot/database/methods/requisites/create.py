from sqlalchemy.ext.asyncio import AsyncSession

from database.models.requisites import Requisites


async def create_requisites(
    session: AsyncSession,
    details: str,
) -> Requisites:
    """
    Создает новые реквизиты в базе данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        details: Подробная информация о реквизитах

    Returns:
        Созданный объект Requisites
    """
    requisites = Requisites(
        details=details,
    )
    session.add(requisites)
    await session.flush()
    await session.refresh(requisites)
    return requisites
