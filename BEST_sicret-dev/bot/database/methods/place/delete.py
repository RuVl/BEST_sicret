from sqlalchemy.ext.asyncio import AsyncSession

from database.models.place import Place


async def delete_place(
    session: AsyncSession,
    place: Place,
) -> None:
    """
    Удаляет место хранения из базы данных.

    Args:
        session: Асинхронная сессия SQLAlchemy
        place: Объект Place для удаления
    """
    await session.delete(place)
    await session.flush()





