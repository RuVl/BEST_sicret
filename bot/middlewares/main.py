from aiogram import Dispatcher, Router

from includes.fluent import get_fluent_localization
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from middlewares.database import DatabaseMiddleware
from middlewares.drop_nothing import DropEmptyCallbackMiddleware
from middlewares.localization import L10nMw
from middlewares.logging import LoggingMw


def register_middlewares(dp: Dispatcher, dialogs_router: Router = None):
    """
    Регистрация middleware.
    
    Порядок регистрации важен для порядка выполнения:
    - outer_middleware выполняются первыми (в порядке регистрации)
    - обычные middleware выполняются в обратном порядке регистрации
    
    Args:
        dp: Диспетчер
        dialogs_router: Роутер диалогов. Если передан, к нему будет применен
                       DatabaseMiddleware с always_create_session=True,
                       так как все диалоги используют БД.
    """
    # 1. Drop callback data with only space symbol (outer_middleware - выполнится первым)
    dp.callback_query.outer_middleware(DropEmptyCallbackMiddleware())

    # 2. Localization
    locale = get_fluent_localization()
    l10n_mw = L10nMw(locale, L10N_FORMAT_KEY)
    dp.message.outer_middleware(l10n_mw)
    dp.callback_query.outer_middleware(l10n_mw)

    # 3. Database session management (после DropEmptyCallbackMiddleware)
    # Применяем middleware к роутеру диалогов с always_create_session=True,
    # так как все диалоги используют БД
    if dialogs_router is not None:
        db_mw_for_dialogs = DatabaseMiddleware(always_create_session=True)
        dialogs_router.message.middleware(db_mw_for_dialogs)
        dialogs_router.callback_query.middleware(db_mw_for_dialogs)

    # Middleware для роутера команд уже применен в register_handlers
    # (до регистрации на диспетчере, чтобы флаги передавались правильно)

    # 4. Logging handlers (после регистрации DatabaseMiddleware для логирования ошибок)
    # Middleware выполняется в обратном порядке регистрации, поэтому LoggingMW,
    # зарегистрированный после DatabaseMiddleware, выполнится после него и
    # сможет логировать ошибки при работе с сессией БД
    logging_mw = LoggingMw(LOGGING_KEY)
    dp.message.middleware(logging_mw)
    dp.callback_query.middleware(logging_mw)
