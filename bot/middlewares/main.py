from aiogram import Dispatcher

from includes.fluent import get_fluent_localization
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY, DB_SESSION_KEY
from middlewares.database import DatabaseSessionMw
from middlewares.drop_nothing import DropEmptyCallbackMiddleware
from middlewares.localization import L10nMw
from middlewares.logging import LoggingMw


def register_middlewares(dp: Dispatcher):
    # Localization (first for use in other Mw)
    locale = get_fluent_localization()
    l10n_mw = L10nMw(locale, L10N_FORMAT_KEY)
    dp.message.outer_middleware(l10n_mw)
    dp.callback_query.outer_middleware(l10n_mw)

    # Database session in middleware_data
    db_mw = DatabaseSessionMw(DB_SESSION_KEY)
    dp.message.outer_middleware(db_mw)
    dp.callback_query.outer_middleware(db_mw)

    # Drop callback data with only space symbol
    dp.callback_query.outer_middleware(DropEmptyCallbackMiddleware())

    # Logging handlers
    logging_mw = LoggingMw(LOGGING_KEY)
    dp.message.middleware(logging_mw)
    dp.callback_query.middleware(logging_mw)
