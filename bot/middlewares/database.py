from typing import Any, Awaitable, Callable, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram_dialog import DialogManager
from sqlalchemy.ext.asyncio import AsyncSession

from database.main import async_session

# Ключ для хранения сессии в data
SESSION_KEY = 'session'


class DatabaseMiddleware(BaseMiddleware):
    """
    Middleware для управления соединениями с базой данных.
    
    Создает сессию БД только для хэндлеров, помеченных флагом 'requires_db'.
    Если middleware применен к роутеру напрямую (например, для диалогов),
    все хэндлеры в этом роутере автоматически получат сессию.
    """
    
    def __init__(self, always_create_session: bool = False):
        """
        Args:
            always_create_session: Если True, всегда создает сессию без проверки флагов.
                                   Используется при применении middleware к роутеру напрямую.
        """
        self.always_create_session = always_create_session
    
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """
        Открывает сессию БД только если:
        - always_create_session=True (применен к роутеру напрямую), ИЛИ
        - хэндлер помечен флагом requires_db=True
        
        Сессия автоматически закрывается после выполнения хэндлера.
        """
        # Если middleware применен к роутеру напрямую, всегда создаем сессию
        if self.always_create_session:
            return await self._create_session_and_call(handler, event, data)
        
        # Проверяем, не является ли это диалогом (диалоги имеют DialogManager в data)
        # Если это диалог, пропускаем (для диалогов есть отдельный middleware)
        if "dialog_manager" in data or isinstance(data.get("dialog_manager"), DialogManager):
            return await handler(event, data)
        
        # Проверяем флаг хэндлера
        # В aiogram 3.x флаги могут быть в data["flags"] или в handler.flags
        flags = data.get("flags", {})
        # Также проверяем handler.flags, если он есть
        handler_obj = data.get("handler")
        if handler_obj:
            # Проверяем разные способы получения флагов
            if hasattr(handler_obj, "flags"):
                flags = {**flags, **handler_obj.flags}
            elif hasattr(handler_obj, "callback") and hasattr(handler_obj.callback, "__flags__"):
                # Флаги могут быть в __flags__ атрибуте callback
                callback_flags = getattr(handler_obj.callback, "__flags__", {})
                flags = {**flags, **callback_flags}
        
        requires_db = flags.get("requires_db", False)
        
        # Если флаг не установлен, пропускаем middleware
        if not requires_db:
            return await handler(event, data)
        
        # Создаем сессию для хэндлеров с флагом
        return await self._create_session_and_call(handler, event, data)
    
    async def _create_session_and_call(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        """Вспомогательный метод для создания сессии и вызова хэндлера."""
        async with async_session() as session:
            data[SESSION_KEY] = session
            try:
                result = await handler(event, data)
                await session.commit()
                return result
            except Exception:
                await session.rollback()
                raise

