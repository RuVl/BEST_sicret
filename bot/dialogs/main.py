from aiogram import Dispatcher, Router
from aiogram_dialog import setup_dialogs

from dialogs.user import user_dialog_router


def register_dialogs(dp: Dispatcher, router: Router):
    router.include_routers(
        user_dialog_router
    )
    # setup_dialogs will be called after commands are registered
    # to ensure commands have higher priority
