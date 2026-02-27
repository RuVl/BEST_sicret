import asyncio
from typing import List

from database.main import async_session
from database.methods.category.read import get_category_by_name
from database.methods.category.create import create_category


TEST_CATEGORIES: List[str] = [
    "Оборудование (аудио/видео)",
    "Мебель",
    "Инструменты",
    "Компьютерная техника",
    "Материалы для мероприятий",
]


async def seed():
    async with async_session() as session:
        for name in TEST_CATEGORIES:
            existing = await get_category_by_name(session, name)
            if existing:
                print(f"Category exists: {name} (id={existing.id})")
                continue
            created = await create_category(session, name=name)
            await session.commit()
            print(f"Created category: {name} (id={created.id})")


def main():
    asyncio.run(seed())


if __name__ == "__main__":
    main()
