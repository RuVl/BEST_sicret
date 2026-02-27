from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.requisites import Requisites


async def update_requisites(
    session: AsyncSession,
    requisites: Requisites,
    details: Optional[str] = None,
) -> Requisites:
    """
    Обновляет данные реквизитов.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        requisites: Объект Requisites для обновления
        details: Новая информация о реквизитах (опционально)

    Returns:
        Обновленный объект Requisites
    """
    if details is not None:
        requisites.details = details
    
    await session.flush()
    await session.refresh(requisites)
    return requisites
