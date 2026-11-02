from aiogram import Dispatcher, Router
from aiogram_dialog import BgManagerFactory

from dialogs import register_dialogs
from env import settings
from handlers import commands, debug


def register_handlers(dp: Dispatcher) -> BgManagerFactory:
    """
    Register all routers here.
    WARNING: order is important: only the first suitable handler will start.
    """

    # Register aiogram-dialogs on new router
    dialogs_router = Router()
    bg_factory = register_dialogs(dp, dialogs_router)

    dp.include_routers(
        commands.router,
        dialogs_router,  # should be last
    )

    if settings.project.DEBUG:
        dp.include_router(debug.router)

    # Фоновые менеджеры диалогов - для работы с окнами вне апдейтов (например, при старте).
    return bg_factory
