from typing import Literal

from aiogram import F
from aiogram.filters.callback_data import CallbackData


class PaginatorFactory(CallbackData, prefix='paginator'):
	menu: str
	action: Literal['change_page', None]
	page: int

	@classmethod
	def page_changed(cls):
		return cls.filter(F.action == 'change_page')


class TemplateFactory(CallbackData, prefix='template'):
	name: str


class AskDataFactory(CallbackData, prefix='ask_data'):
	parent_type: Literal['object', 'array']
	key: str | int


class ActionDataFactory(CallbackData, prefix='action'):
	action: str
