from typing import Any, Dict

from aiogram_dialog import DialogManager
from sqlalchemy.ext.asyncio import AsyncSession

from middlewares.database import SESSION_KEY


# Функция-хелпер для получения сессии из data в хэндлерах
def get_session(data: Dict[str, Any]) -> AsyncSession:
    """
    Получает сессию БД из data (для обычных хэндлеров).

    Args:
        data: Словарь данных из middleware

    Returns:
        AsyncSession объект

    Raises:
        KeyError: Если сессия не найдена в data
    """
    return data[SESSION_KEY]


# Функция-хелпер для получения сессии из dialog_manager в диалогах
def get_session_from_dialog_manager(dialog_manager: DialogManager) -> AsyncSession:
    """
    Получает сессию БД из dialog_manager.middleware_data (для диалогов).

    Args:
        dialog_manager: Диспетчер диалогов

    Returns:
        AsyncSession объект

    Raises:
        KeyError: Если сессия не найдена в middleware_data
    """
    return dialog_manager.middleware_data[SESSION_KEY]

