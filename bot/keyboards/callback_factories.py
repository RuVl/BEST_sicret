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


class AskActionFactory(CallbackData, prefix='ask_action'):
    data: str
    type: str
