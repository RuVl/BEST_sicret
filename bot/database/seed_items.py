import asyncio
from database.main import async_session
from database.methods.category.read import get_all_categories
from database.methods.item.create import create_item
from database.methods.place.create import create_place
from database.methods.person.read import get_person_by_id

# Тестовые предметы для каждой категории
ITEMS_BY_CATEGORY = {
    "Оборудование (аудио/видео)": [
        {"name": "Микрофон", "count": 5, "unit": "шт"},
        {"name": "Проектор", "count": 2, "unit": "шт"},
    ],
    "Мебель": [
        {"name": "Стул", "count": 20, "unit": "шт"},
        {"name": "Стол", "count": 5, "unit": "шт"},
    ],
    "Инструменты": [
        {"name": "Отвертка", "count": 10, "unit": "шт"},
        {"name": "Молоток", "count": 4, "unit": "шт"},
    ],
    "Компьютерная техника": [
        {"name": "Ноутбук", "count": 3, "unit": "шт"},
        {"name": "Монитор", "count": 6, "unit": "шт"},
    ],
    "Материалы для мероприятий": [
        {"name": "Бумага", "count": 100, "unit": "лист"},
        {"name": "Маркер", "count": 15, "unit": "шт"},
    ],
}

# ID пользователя, у которого будет создано место хранения (замените на реальный ID, если нужно)
TEST_PERSON_ID = 1

async def seed_items():
    async with async_session() as session:
        # Получаем или создаём тестовое место хранения
        from database.methods.place.read import get_place_by_id
        place = await get_place_by_id(session, 1)
        if not place:
            from database.methods.place.create import create_place
            place = await create_place(session, address="Склад 1", person_id=TEST_PERSON_ID)
            await session.commit()
        place_id = place.id

        # Получаем все категории
        categories = await get_all_categories(session)
        for category in categories:
            items = ITEMS_BY_CATEGORY.get(category.name, [])
            for item in items:
                await create_item(
                    session,
                    name=item["name"],
                    count=item["count"],
                    unit=item["unit"],
                    category_id=category.id,
                    place_id=place_id,
                )
                print(f"Добавлен предмет '{item['name']}' в категорию '{category.name}'")
            await session.commit()

def main():
    asyncio.run(seed_items())

if __name__ == "__main__":
    main()