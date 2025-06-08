from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from fluent.runtime import FluentLocalization


class L10nMw(BaseMiddleware):
	def __init__(self, locale: FluentLocalization, middleware_key="l10n"):
		self.locale = locale
		self.middleware_key = middleware_key

	async def __call__(
			self,
			handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
			event: TelegramObject,
			data: dict[str, Any]
	) -> Any:
		data[self.middleware_key] = self.locale
		return await handler(event, data)
