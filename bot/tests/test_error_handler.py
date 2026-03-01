"""
Тесты для модуля обработки ошибок БД (error_handler.py)

Тестирует:
- Обработку IntegrityError (дублирование, foreign key)
- Обработку OperationalError (проблемы с подключением)
- Обработку DataError (неверные данные)
- Корректный rollback
- Локализацию сообщений об ошибках
"""

import sys
import os
from pathlib import Path

# Добавляем корневую папку проекта в PYTHONPATH
bot_root = Path(__file__).parent.parent
sys.path.insert(0, str(bot_root))

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.exc import IntegrityError, OperationalError, DataError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

# Вам нужно будет установить эти зависимости для тестирования:
# pip install pytest pytest-asyncio pytest-mock


class MockFluentLocalization:
    """Mock объект для FluentLocalization"""
    def format_value(self, key, args=None):
        messages = {
            'db-error-duplicate-entry': 'Такая запись уже существует',
            'db-error-connection': 'Ошибка подключения к БД',
            'db-error-data': 'Ошибка данных',
            'db-error-unknown': 'Непредвиденная ошибка БД',
            'db-error-foreign-key': f'Ошибка связи при операции: {args.get("operation") if args else "unknown"}',
        }
        return messages.get(key, 'Неизвестная ошибка')


@pytest.mark.asyncio
async def test_handle_db_commit_success():
    """Тест успешного commit"""
    from database.error_handler import handle_db_commit
    
    session = AsyncMock(spec=AsyncSession)
    session.commit = AsyncMock()
    l10n = MockFluentLocalization()
    
    success, error_msg = await handle_db_commit(session, l10n, "test operation")
    
    assert success is True
    assert error_msg is None
    session.commit.assert_called_once()
    session.rollback.assert_not_called()


@pytest.mark.asyncio
async def test_handle_db_commit_integrity_error_duplicate():
    """Тест обработки IntegrityError - дублирование записи"""
    from database.error_handler import handle_db_commit
    
    session = AsyncMock(spec=AsyncSession)
    session.rollback = AsyncMock()
    
    # Создаем исключение с правильными атрибутами
    orig_exc = Exception("Duplicate entry 'test' for key 'unique_constraint'")
    exc = IntegrityError(
        statement="INSERT INTO ...",
        params={},
        orig=orig_exc
    )
    session.commit = AsyncMock(side_effect=exc)
    l10n = MockFluentLocalization()
    
    success, error_msg = await handle_db_commit(session, l10n, "create person")
    
    assert success is False
    assert 'уже существует' in error_msg
    session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_handle_db_commit_integrity_error_foreign_key():
    """Тест обработки IntegrityError - нарушение foreign key"""
    from database.error_handler import handle_db_commit
    
    session = AsyncMock(spec=AsyncSession)
    session.rollback = AsyncMock()
    
    # Создаем исключение с правильными атрибутами
    orig_exc = Exception("Foreign key constraint failed")
    exc = IntegrityError(
        statement="INSERT INTO ...",
        params={},
        orig=orig_exc
    )
    session.commit = AsyncMock(side_effect=exc)
    l10n = MockFluentLocalization()
    
    success, error_msg = await handle_db_commit(session, l10n, "create refund")
    
    assert success is False
    assert 'связи' in error_msg or 'foreign' in error_msg.lower()
    session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_handle_db_commit_operational_error():
    """Тест обработки OperationalError - проблемы подключения"""
    from database.error_handler import handle_db_commit
    
    session = AsyncMock(spec=AsyncSession)
    session.rollback = AsyncMock()
    
    exc = OperationalError("Connection refused", None, None)
    session.commit = AsyncMock(side_effect=exc)
    l10n = MockFluentLocalization()
    
    success, error_msg = await handle_db_commit(session, l10n, "query database")
    
    assert success is False
    assert 'подключения' in error_msg or 'connection' in error_msg.lower()
    session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_handle_db_commit_data_error():
    """Тест обработки DataError - неверные данные"""
    from database.error_handler import handle_db_commit
    
    session = AsyncMock(spec=AsyncSession)
    session.rollback = AsyncMock()
    
    exc = DataError("Invalid data type", None, None)
    session.commit = AsyncMock(side_effect=exc)
    l10n = MockFluentLocalization()
    
    success, error_msg = await handle_db_commit(session, l10n, "insert data")
    
    assert success is False
    assert 'данных' in error_msg or 'data' in error_msg.lower()
    session.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_handle_db_commit_unexpected_error():
    """Тест обработки неожиданных ошибок"""
    from database.error_handler import handle_db_commit
    
    session = AsyncMock(spec=AsyncSession)
    session.rollback = AsyncMock()
    
    exc = RuntimeError("Something went wrong")
    session.commit = AsyncMock(side_effect=exc)
    l10n = MockFluentLocalization()
    
    success, error_msg = await handle_db_commit(session, l10n, "unknown operation")
    
    assert success is False
    assert error_msg is not None
    session.rollback.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
