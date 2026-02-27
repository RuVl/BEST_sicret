from sqlalchemy.ext.asyncio import AsyncSession

from database.models.item import Item


async def delete_item(
    session: AsyncSession,
    item: Item,
) -> None:
    """
    Удаляет товар из базы данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        item: Объект Item для удаления
    """
    session.delete(item)
    await session.flush()

