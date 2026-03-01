"""
Интеграционный тест для error_handler.py

Этот скрипт тестирует обработку ошибок БД реальными ошибками SQLAlchemy.
Запустите его с помощью: python test_error_handler_integration.py
"""

import sys
import os
from pathlib import Path
import asyncio
import logging

# Добавляем корневую папку проекта в PYTHONPATH
bot_root = Path(__file__).parent.parent
sys.path.insert(0, str(bot_root))

from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import IntegrityError

from database.error_handler import handle_db_commit

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

Base = declarative_base()


class TestUser(Base):
    """Тестовая модель пользователя"""
    __tablename__ = 'test_users'
    
    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, nullable=False)
    email = Column(String(100), nullable=False)


class MockL10n:
    """Mock локализация для тестирования"""
    def format_value(self, key, args=None):
        messages = {
            'db-error-duplicate-entry': '❌ Ошибка: такая запись уже существует',
            'db-error-connection': '❌ Проблема с подключением к БД',
            'db-error-data': '❌ Ошибка в данных',
            'db-error-unknown': '❌ Неизвестная ошибка БД',
        }
        return messages.get(key, f'Ошибка: {key}')


async def test_duplicate_entry():
    """Тест: дублирование записи (IntegrityError)"""
    print("\n" + "="*60)
    print("TEST 1: Обработка дублирования записи (IntegrityError)")
    print("="*60)
    
    # Используем SQLite для тестирования (в памяти)
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_factory() as session:
        l10n = MockL10n()
        
        # Добавляем первого пользователя
        user1 = TestUser(username='john', email='john@example.com')
        session.add(user1)
        await session.commit()
        print("Первый пользователь создан успешно")
        
        # Пытаемся добавить пользователя с тем же username
        user2 = TestUser(username='john', email='john2@example.com')
        session.add(user2)
        
        success, error_msg = await handle_db_commit(session, l10n, "create duplicate user")
        
        print(f"Результат: {'SUCCESS' if success else 'COMMIT FAILED'}")
        if not success:
            print(f"Сообщение ошибки: {error_msg}")
            assert 'существует' in error_msg.lower(), "Ошибка должна упоминать дубликат"
            print("Ошибка обработана корректно")
        else:
            print("ОШИБКА: commit не должен был пройти!")
    
    await engine.dispose()


async def test_successful_commit():
    """Тест: успешный commit"""
    print("\n" + "="*60)
    print("TEST 2: Успешный commit")
    print("="*60)
    
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_factory() as session:
        l10n = MockL10n()
        
        user = TestUser(username='alice', email='alice@example.com')
        session.add(user)
        
        success, error_msg = await handle_db_commit(session, l10n, "create user")
        
        print(f"Результат: {'SUCCESS' if success else 'FAILED'}")
        assert success is True, "Commit должен был пройти"
        assert error_msg is None, "Не должно быть ошибки"
        print("Commit прошел успешно")
    
    await engine.dispose()


async def test_transaction_rollback():
    """Тест: откат транзакции при ошибке"""
    print("\n" + "="*60)
    print("TEST 3: Откат транзакции при ошибке")
    print("="*60)
    
    engine = create_async_engine('sqlite+aiosqlite:///:memory:', echo=False)
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session_factory() as session:
        l10n = MockL10n()
        
        # Создаем первого пользователя
        user1 = TestUser(username='bob', email='bob@example.com')
        session.add(user1)
        await session.commit()
        
        # Пытаемся создать дубликат
        user2 = TestUser(username='bob', email='bob2@example.com')
        session.add(user2)
        
        success, error_msg = await handle_db_commit(session, l10n, "create duplicate")
        
        assert success is False, "Commit должен был упасть"
        print(f"Commit упал как ожидалось: {error_msg}")
        
        # Проверяем что в сессии нет висящих изменений
        print(f"Объекты в сессии: {len(session.new)} новых, {len(session.dirty)} измененных")
        assert len(session.new) == 0, "После rollback не должно быть новых объектов"
        print("Транзакция откатилась корректно")
    
    await engine.dispose()


async def run_all_tests():
    """Запустить все тесты"""
    print("\n" + "🧪 "*30)
    print("ИНТЕГРАЦИОННОЕ ТЕСТИРОВАНИЕ error_handler.py")
    print("🧪 "*30)
    
    try:
        await test_successful_commit()
        await test_duplicate_entry()
        await test_transaction_rollback()
        
        print("\n" + "="*60)
        print("ВСЕ ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО")
        print("="*60 + "\n")
        
    except AssertionError as e:
        print(f"\nТЕСТ НЕ ПРОЙДЕН: {e}\n")
        raise
    except Exception as e:
        print(f"\nОШИБКА ВО ВРЕМЯ ТЕСТИРОВАНИЯ: {e}\n")
        raise


if __name__ == '__main__':
    asyncio.run(run_all_tests())
