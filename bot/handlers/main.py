from aiogram import Dispatcher, Router
from aiogram_dialog import setup_dialogs

from dialogs import register_dialogs
from handlers import commands
from middlewares.database import DatabaseMiddleware


def register_handlers(dp: Dispatcher):
    """
    Register all routers here.
    WARNING: order is important: only the first suitable handler will start.
    
    Returns:
        tuple: (dialogs_router, commands_router) - роутеры для применения middleware
    """

    # Применяем middleware к роутеру команд ДО регистрации на диспетчере
    # Это важно для правильной передачи флагов
    db_mw_for_handlers = DatabaseMiddleware(always_create_session=False)
    commands.router.message.middleware(db_mw_for_handlers)
    commands.router.callback_query.middleware(db_mw_for_handlers)

    # Register commands router first to ensure commands are processed before dialogs
    # Commands should have higher priority than dialogs
    dp.include_routers(
        commands.router  # Commands first - higher priority
    )

    # Register aiogram-dialogs on new router
    dialogs_router = Router()
    register_dialogs(dp, dialogs_router)
    
    # Register dialogs router after commands
    dp.include_routers(
        dialogs_router  # Dialogs last - lower priority
    )
    
    # Setup dialogs AFTER commands are registered to ensure commands have higher priority
    setup_dialogs(dp)
    
    return dialogs_router, commands.router
