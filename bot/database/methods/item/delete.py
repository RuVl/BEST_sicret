from sqlalchemy.ext.asyncio import AsyncSession

from database.models.item import Item


async def delete_item(
    session: AsyncSession,
    item: Item,
) -> None:
    """
    Удаляет товар из базы данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        item: Объект Item для удаления
    """
    await session.delete(item)
    await session.flush()

