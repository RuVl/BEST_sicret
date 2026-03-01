"""
Вспомогательный скрипт для тестирования ошибок БД.

Помогает вызвать разные типы ошибок в реальной БД для проверки
обработки в error_handler.py

Использование:
    python bot/tests/test_db_errors.py --error-type duplicate
    python bot/tests/test_db_errors.py --error-type connection
    python bot/tests/test_db_errors.py --error-type data
"""

import sys
import os
from pathlib import Path
import asyncio
import argparse
import logging

# Добавляем корневую папку проекта в PYTHONPATH
bot_root = Path(__file__).parent.parent
sys.path.insert(0, str(bot_root))

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируйте ваши модели и сессии
# from database.main import async_session
# from database.models import Person

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_duplicate_error():
    """
    Тестирует обработку IntegrityError - дублирование записи.
    
    ВНИМАНИЕ: требует прямого доступа к БД
    """
    print("\n" + "="*60)
    print("TEST: IntegrityError - Дублирование записи")
    print("="*60)
    print("Это попытается создать две записи с одинаковым email...")
    
    from database.main import async_session
    from database.models import Person
    from database.error_handler import handle_db_commit
    from fluent import FluentLocalization
    
    async with async_session() as session:
        # Создаем mock локализацию
        class MockL10n:
            def format_value(self, key, args=None):
                messages = {
                    'db-error-duplicate-entry': 'Такая запись уже существует',
                    'db-error-foreign-key': 'Ошибка связи данных',
                }
                return messages.get(key, f'Ошибка БД')
        
        l10n = MockL10n()
        
        # Создаем первого пользователя
        person1 = Person(
            telegram_id=123456789,
            full_name="Test User 1"
        )
        session.add(person1)
        success, msg = await handle_db_commit(session, l10n, "create person 1")
        print(f"\n1️ Первый пользователь: {'✅' if success else '❌'} {msg or 'успех'}")
        
        # Пытаемся создать второго с тем же telegram_id
        person2 = Person(
            telegram_id=123456789,  # ДУБЛИКАТ!
            full_name="Test User 2"
        )
        session.add(person2)
        success, msg = await handle_db_commit(session, l10n, "create duplicate person")
        print(f"2️⃣ Второй пользователь: {'✅' if success else '❌'} {msg or 'успех'}")
        
        if not success:
            print(f"Ошибка обработана корректно: {msg}")
        else:
            print(f"Второй пользователь был создан (проверьте unique constraint)")


async def test_manual_query_error():
    """
    Тестирует через неправильный SQL запрос.
    Примеры для вызова разных ошибок вручную.
    """
    print("\n" + "="*60)
    print("TEST: Ошибка при неправильном SQL запросе")
    print("="*60)
    
    from database.main import async_session
    from database.error_handler import safe_commit
    
    async with async_session() as session:
        try:
            # Пример: неправильный column
            await session.execute(text("SELECT nonexistent_column FROM persons"))
            await session.commit()
        except Exception as e:
            print(f"\n Ошибка SQL: {type(e).__name__}")
            print(f"Сообщение: {str(e)[:100]}")
            print(f" Исключение было поднято (correct behavior)")


async def test_connection_recovery():
    """
    Тестирует восстановление после ошибки подключения.
    
    ВНИМАНИЕ: Требует остановки БД!
    
    Инструкции:
    1. Запустите этот скрипт
    2. Когда увидите "ОСТАНОВИТЕ БД СЕЙЧАС", выполните в другом терминале:
       docker-compose down db
    3. Нажмите Enter в этом терминале
    4. Когда увидите "ЗАПУСТИТЕ БД", выполните:
       docker-compose up -d db
    5. Нажмите Enter и смотрите результаты
    """
    print("\n" + "="*60)
    print("TEST: Восстановление от OperationalError")
    print("="*60)
    
    print("\nДля этого теста нужна ваша помощь!")
    print("Когда скрипт попросит - остановите БД и запустите её обратно.")
    
    input("\nНажмите Enter когда БД работает нормально...")
    
    from database.main import async_session
    
    # Первое успешное подключение
    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
            print("\nПодключение 1: успешно")
    except Exception as e:
        print(f"\nПодключение 1 упало: {e}")
    
    # Просим остановить БД
    print("\n🛑 ОСТАНОВИТЕ БД СЕЙЧАС:")
    print("   docker-compose down db")
    input("▶️  Нажмите Enter когда БД остановлена...")
    
    # Попытка подключения при остановленной БД
    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
            print("\nПодключение 2: работает (БД еще не остановилась?)")
    except Exception as e:
        print(f"\nПодключение 2: упало как ожидалось")
        print(f"Тип ошибки: {type(e).__name__}")
    
    # Просим запустить БД
    print("\nЗАПУСТИТЕ БД:")
    print("   docker-compose up -d db")
    print("   sleep 5  # Ждем инициализации")
    input("Нажмите Enter когда БД запустилась...")
    
    # Попытка подключения после восстановления БД
    await asyncio.sleep(2)  # Даем БД время на старт
    
    try:
        async with async_session() as session:
            result = await session.execute(text("SELECT 1"))
            print(f"\nПодключение 3: восстановилось успешно!")
    except Exception as e:
        print(f"\nПодключение 3 еще не работает: {e}")
        print("Дайте БД еще времени на старт...")


def print_help():
    """Выводит справку с примерами"""
    print("""
╔════════════════════════════════════════════════════════════════╗
║   Примеры для тестирования ошибок обработчика                 ║
╚════════════════════════════════════════════════════════════════╝

1️  UNIT ТЕСТЫ (рекомендуемый способ):
    pytest bot/tests/test_error_handler.py -v

2️  ИНТЕГРАЦИОННЫЕ ТЕСТЫ (с реальной БД):
    python bot/tests/test_error_handler_integration.py

3️  РУЧНЫЕ ТЕСТЫ (этот скрипт):
    
    # Дублирование записи (IntegrityError)
    python bot/tests/test_db_errors.py --error-type duplicate
    
    # Неправильный SQL (DataError)
    python bot/tests/test_db_errors.py --error-type data
    
    # Потеря соединения (OperationalError)
    python bot/tests/test_db_errors.py --error-type connection

4️ ЧЕРЕЗ ТГ БОТ (самый реалистичный):
    
    a) Дублирование при /start:
       - Откройте бот из двух аккаунтов с одинаковым ID
       - Оба пошлют /start одновременно
    
    b) Потеря соединения при /request_refund:
       - Заполните форму
       - docker-compose down db
       - Нажмите "Подтвердить"
       - Проверьте сообщение об ошибке

5️  ПРОВЕРКА ЛОГОВ:
    
    # Следить за логами в реальном времени
    docker-compose logs -f bot
    
    # Или через контейнер
    docker logs -f best_sicret_bot

6️  ЧТЕНИЕ БД НАПРЯМУЮ:
    
    # Подключиться к PostgreSQL
    docker-compose exec db psql -U postgres -d best_db
    
    # Посмотреть последние ошибки
    SELECT * FROM persons ORDER BY id DESC;
    SELECT * FROM refunds ORDER BY id DESC;
    """)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Тестирование обработки ошибок БД',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='Примеры:\n  python test_db_errors.py --error-type duplicate\n  python test_db_errors.py --help'
    )
    
    parser.add_argument(
        '--error-type',
        choices=['duplicate', 'data', 'connection'],
        help='Тип ошибки для тестирования'
    )
    
    parser.add_argument(
        '--help-all',
        action='store_true',
        help='Показать всю справку с примерами'
    )
    
    args = parser.parse_args()
    
    if args.help_all:
        print_help()
    elif args.error_type == 'duplicate':
        asyncio.run(test_duplicate_error())
    elif args.error_type == 'data':
        asyncio.run(test_manual_query_error())
    elif args.error_type == 'connection':
        asyncio.run(test_connection_recovery())
    else:
        print_help()
