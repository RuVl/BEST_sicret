from typing import Callable, Any, Awaitable

from aiogram import BaseMiddleware, types
from aiogram.dispatcher.event.bases import CancelHandler
from aiogram_dialog.api.exceptions import UnknownIntent
from fluent.runtime import FluentLocalization

from middlewares import L10N_FORMAT_KEY


class DropEmptyCallbackMiddleware(BaseMiddleware):
    """ Auto answer and drop events with callback data is space """

    async def __call__(self,
                       handler: Callable[[types.CallbackQuery, dict[str, Any]], Awaitable[Any]],
                       event: types.CallbackQuery,
                       data: dict[str, Any],
                       ) -> Any:
        if event.data == ' ':
            await event.answer()
            return CancelHandler()

        try:
            return await handler(event, data)
        except UnknownIntent:  # If we lose user's dialog state - we remove reply_markup
            await event.message.delete_reply_markup()

            l10n: FluentLocalization = data[L10N_FORMAT_KEY]
            await event.answer(l10n.format_value('invalid-stack'))
