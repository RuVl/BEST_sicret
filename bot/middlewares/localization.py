from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import Message, CallbackQuery
from fluent.runtime import FluentLocalization


class L10nMiddleware(BaseMiddleware):
    def __init__(self, locale: FluentLocalization):
        self.locale = locale

    async def __call__(
            self,
            handler: Callable[[Message | CallbackQuery, Dict[str, Any]], Awaitable[Any]],
            event: Message | CallbackQuery,
            data: Dict[str, Any]
    ) -> Any:
        data["l10n"] = self.locale
        return await handler(event, data)
