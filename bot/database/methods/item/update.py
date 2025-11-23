from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from database.models.item import Item


async def update_item(
    session: AsyncSession,
    item: Item,
    name: Optional[str] = None,
    count: Optional[int] = None,
    unit: Optional[str] = None,
    category_id: Optional[int] = None,
    place_id: Optional[int] = None,
) -> Item:
    """
    Обновляет данные товара.

    Args:
        session: Асинхронная сессия SQLAlchemy
        item: Объект Item для обновления
        name: Новое название товара (опционально)
        count: Новое количество (опционально)
        unit: Новая единица измерения (опционально)
        category_id: Новый ID категории (опционально)
        place_id: Новый ID места хранения (опционально)

    Returns:
        Обновленный объект Item
    """
    if name is not None:
        item.name = name
    if count is not None:
        item.count = count
    if unit is not None:
        item.unit = unit
    if category_id is not None:
        item.category_id = category_id
    if place_id is not None:
        item.place_id = place_id
    
    await session.flush()
    await session.refresh(item)
    return item

