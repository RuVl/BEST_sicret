from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from database.main import async_session


class DatabaseSessionMw(BaseMiddleware):
    def __init__(self, middleware_key: str = "db_session"):
        self.middleware_key = middleware_key

    async def __call__(
            self,
            handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
            event: TelegramObject,
            data: dict[str, Any]
    ) -> Any:
        async with async_session() as session:
            data[self.middleware_key] = session
            return await handler(event, data)
