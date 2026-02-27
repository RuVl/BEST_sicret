from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import insert

from database.models.application import Application, application_item


async def create_application(
    session: AsyncSession,
    person_id: int,
    applicant_name: str,
    purpose: str,
    items_with_quantities: dict[int, int],  # Словарь {item_id: quantity}
) -> Application:
    """
    Создает новую заявку на использование имущества.
    
    Стратегия: этот метод использует FLUSH без COMMIT.
    Коммит выполняется на уровне middleware или обработчика.

    Args:
        session: Асинхронная сессия SQLAlchemy
        person_id: ID пользователя, создающего заявку
        applicant_name: Имя заявителя
        purpose: Цель взятия имущества
        items_with_quantities: Словарь {item_id: quantity}

    Returns:
        Созданный объект Application
    """
    application = Application(
        person_id=person_id,
        applicant_name=applicant_name,
        purpose=purpose,
        status='pending'
    )
    session.add(application)
    await session.flush()
    await session.refresh(application)

    # Добавляем предметы с количествами через промежуточную таблицу
    for item_id, quantity in items_with_quantities.items():
        stmt = insert(application_item).values(
            application_id=application.id,
            item_id=item_id,
            quantity=quantity
        )
        await session.execute(stmt)

    await session.refresh(application)
    return application


