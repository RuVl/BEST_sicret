from sqlalchemy.ext.asyncio import AsyncSession

from database.models.item import Item


async def create_item(
    session: AsyncSession,
    name: str,
    count: int,
    unit: str,
    category_id: int,
    place_id: int,
) -> Item:
    """
    Создает новый товар в базе данных.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        name: Название товара
        count: Количество товара
        unit: Единица измерения
        category_id: ID категории
        place_id: ID места хранения

    Returns:
        Созданный объект Item
    """
    item = Item(
        name=name,
        count=count,
        unit=unit,
        category_id=category_id,
        place_id=place_id,
    )
    session.add(item)
    await session.flush()
    await session.refresh(item)
    return item





