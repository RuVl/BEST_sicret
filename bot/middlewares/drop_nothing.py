from typing import Callable, Any, Awaitable

from aiogram import BaseMiddleware, types
from aiogram.dispatcher.event.bases import CancelHandler


class DropNothingButtonMiddleware(BaseMiddleware):
    """ Auto answer and drop events with callback data == 'nothing' """

    async def __call__(self,
                       handler: Callable[[types.CallbackQuery, dict[str, Any]], Awaitable[Any]],
                       event: types.CallbackQuery,
                       data: dict[str, Any],
                       ) -> Any:
        if event.data == 'nothing':
            await event.answer()
            return CancelHandler()

        return await handler(event, data)
