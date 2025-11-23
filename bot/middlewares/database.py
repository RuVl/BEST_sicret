from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from database.main import async_session

# Ключ для хранения сессии в data
SESSION_KEY = 'session'


class DatabaseMiddleware(BaseMiddleware):
    """Middleware для управления соединениями с базой данных."""
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Открывает сессию БД для каждого запроса и передает её в хэндлеры через data['session'].
        Сессия автоматически закрывается после выполнения хэндлера.
        """
        async with async_session() as session:
            data[SESSION_KEY] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

