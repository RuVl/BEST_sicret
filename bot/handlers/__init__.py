from aiogram import Dispatcher

from bot.handlers import main
from bot.handlers import templates


def register_handlers(dp: Dispatcher):
    """
    Register all routers here.
    WARNING: order is important. Only the first suitable handler will start.
    """

    dp.include_router(main.router)
    dp.include_router(templates.router)
