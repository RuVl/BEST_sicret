"""
Централизованная обработка ошибок базы данных.

Этот модуль решает ПРОБЛЕМУ 6: Обработка ошибок БД — дублирование логики.

Вместо дублирования try/except блоков в каждом handler'е,
предоставляем централизованные инструменты:
- handle_db_commit() - функция для безопасного commit с обработкой ошибок
- @handle_db_errors - декоратор для handler функций
"""

import logging
from typing import Callable, Any, Optional
from functools import wraps

from sqlalchemy.exc import (
    IntegrityError,
    OperationalError,
    DataError,
    DatabaseError,
    SQLAlchemyError
)
from sqlalchemy.ext.asyncio import AsyncSession
from fluent.runtime import FluentLocalization

logger = logging.getLogger(__name__)


class DatabaseErrorType:
    """Типы ошибок базы данных для l10n"""
    DUPLICATE_ENTRY = 'db-error-duplicate-entry'
    CONNECTION_ERROR = 'db-error-connection'
    DATA_ERROR = 'db-error-data'
    UNKNOWN_ERROR = 'db-error-unknown'


async def handle_db_commit(
    session: AsyncSession,
    l10n: FluentLocalization,
    operation_name: str = "database operation"
) -> tuple[bool, Optional[str]]:
    """
    Безопасный commit с централизованной обработкой ошибок БД.
    
    Args:
        session: Активная сессия SQLAlchemy
        l10n: Объект локализации для сообщений
        operation_name: Название операции для логирования
    
    Returns:
        Tuple (success: bool, error_message: Optional[str])
        - (True, None) если commit успешен
        - (False, error_message) если произошла ошибка
    
    Примеры использования:
        >>> success, error_msg = await handle_db_commit(session, l10n, "create user")
        >>> if not success:
        >>>     await callback.answer(error_msg, show_alert=True)
        >>>     return
    """
    try:
        await session.commit()
        logger.info(f"Successfully committed: {operation_name}")
        return True, None
        
    except IntegrityError as e:
        await session.rollback()
        logger.error(f"IntegrityError in {operation_name}: {str(e)}")
        
        # Определяем тип нарушения целостности
        error_msg = str(e.orig).lower()
        if 'unique' in error_msg or 'duplicate' in error_msg:
            return False, l10n.format_value(DatabaseErrorType.DUPLICATE_ENTRY)
        elif 'foreign key' in error_msg:
            return False, l10n.format_value(
                'db-error-foreign-key',
                args={'operation': operation_name}
            )
        else:
            return False, l10n.format_value(DatabaseErrorType.DATA_ERROR)
    
    except OperationalError as e:
        await session.rollback()
        logger.error(f"OperationalError in {operation_name}: {str(e)}")
        return False, l10n.format_value(DatabaseErrorType.CONNECTION_ERROR)
    
    except DataError as e:
        await session.rollback()
        logger.error(f"DataError in {operation_name}: {str(e)}")
        return False, l10n.format_value(DatabaseErrorType.DATA_ERROR)
    
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"SQLAlchemyError in {operation_name}: {str(e)}")
        return False, l10n.format_value(DatabaseErrorType.UNKNOWN_ERROR)
    
    except Exception as e:
        await session.rollback()
        logger.error(f"Unexpected error in {operation_name}: {str(e)}")
        return False, l10n.format_value(DatabaseErrorType.UNKNOWN_ERROR)


def handle_db_errors(operation_name: str = "database operation"):
    """
    Декоратор для автоматической обработки ошибок БД в handler функциях.
    
    Автоматически оборачивает функцию в try/except с обработкой ошибок commit.
    При ошибке откатывает транзакцию и отправляет пользователю сообщение.
    
    Args:
        operation_name: Название операции для логирования
    
    Примеры использования:
        >>> @handle_db_errors(operation_name="create refund")
        >>> async def on_confirm_application(clb: CallbackQuery, ...):
        >>>     # ... код с session.commit() ...
        >>>     await session.commit()  # Будет обработано декоратором
    
    ВАЖНО: Декоратор ожидает, что в kwargs функции есть:
    - 'dialog_manager' (DialogManager) - для доступа к middleware_data
    - В middleware_data должны быть SESSION_KEY и L10N_FORMAT_KEY
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Извлекаем необходимые зависимости
            dialog_manager = kwargs.get('dialog_manager')
            if not dialog_manager:
                # Если нет dialog_manager, пропускаем декоратор
                logger.warning(
                    f"handle_db_errors decorator used on {func.__name__} "
                    "without dialog_manager - skipping error handling"
                )
                return await func(*args, **kwargs)
            
            session: AsyncSession = dialog_manager.middleware_data.get('session')
            l10n: FluentLocalization = dialog_manager.middleware_data.get('l10n_format')
            
            if not session or not l10n:
                logger.warning(
                    f"Missing session or l10n in middleware_data for {func.__name__}"
                )
                return await func(*args, **kwargs)
            
            try:
                # Выполняем оригинальную функцию
                result = await func(*args, **kwargs)
                return result
                
            except IntegrityError as e:
                await session.rollback()
                logger.error(f"IntegrityError in {operation_name} ({func.__name__}): {str(e)}")
                
                # Получаем callback для ответа пользователю
                clb = args[0] if args and hasattr(args[0], 'answer') else None
                if clb:
                    error_msg = l10n.format_value(DatabaseErrorType.DUPLICATE_ENTRY)
                    await clb.answer(error_msg, show_alert=True)
                raise
            
            except OperationalError as e:
                await session.rollback()
                logger.error(f"OperationalError in {operation_name} ({func.__name__}): {str(e)}")
                
                clb = args[0] if args and hasattr(args[0], 'answer') else None
                if clb:
                    error_msg = l10n.format_value(DatabaseErrorType.CONNECTION_ERROR)
                    await clb.answer(error_msg, show_alert=True)
                raise
            
            except (DataError, SQLAlchemyError) as e:
                await session.rollback()
                logger.error(f"Database error in {operation_name} ({func.__name__}): {str(e)}")
                
                clb = args[0] if args and hasattr(args[0], 'answer') else None
                if clb:
                    error_msg = l10n.format_value(DatabaseErrorType.UNKNOWN_ERROR)
                    await clb.answer(error_msg, show_alert=True)
                raise
        
        return wrapper
    return decorator


async def safe_commit(
    session: AsyncSession,
    operation_name: str = "database operation"
) -> None:
    """
    Простой commit с логированием, без обработки ошибок.
    Используйте для простых случаев, где не нужна обработка на месте.
    
    Args:
        session: Активная сессия SQLAlchemy
        operation_name: Название операции для логирования
    
    Raises:
        SQLAlchemyError: При любой ошибке БД (для обработки на верхнем уровне)
    """
    try:
        await session.commit()
        logger.info(f"Successfully committed: {operation_name}")
    except SQLAlchemyError as e:
        await session.rollback()
        logger.error(f"Failed to commit {operation_name}: {str(e)}")
        raise
