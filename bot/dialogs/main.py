from aiogram import Dispatcher, Router
from aiogram.enums import ParseMode
from aiogram.filters import ExceptionTypeFilter
from aiogram.types import ErrorEvent
from aiogram_dialog import DialogManager, setup_dialogs
from aiogram_dialog.api.exceptions import UnknownIntent, UnknownState
from structlog import getLogger
from structlog.typing import FilteringBoundLogger

from dialogs.user import user_dialog_router
from includes.memory_media import MemoryMediaMessageManager
from middlewares.main import register_dialog_update_middlewares

logger: FilteringBoundLogger = getLogger("dialogs")


def register_dialogs(dp: Dispatcher, router: Router):
    router.errors.register(
        on_unknown_state_or_intent,
        ExceptionTypeFilter(UnknownState, UnknownIntent),
    )

    router.include_routers(
        user_dialog_router,
    )

    # Свой MessageManager: окна могут показывать файлы из памяти (конфиги AmneziaWG) без диска
    setup_dialogs(dp, message_manager=MemoryMediaMessageManager())  # Register on dispatcher for using anywhere
    register_dialog_update_middlewares(dp)


async def on_unknown_state_or_intent(event: ErrorEvent, dialog_manager: DialogManager):
    await dialog_manager.reset_stack()
    await logger.aerror(
        "Unknown state or intent of aiogram's dialog. Reset stack.",
        error=str(event.exception),
    )

    update = event.update
    err_msg = "Bot has been updated or something broken. Please try again."

    if update.callback_query:
        await update.callback_query.answer(err_msg, show_alert=True)
    elif update.message:
        await update.message.answer(err_msg, parse_mode=ParseMode.HTML)
