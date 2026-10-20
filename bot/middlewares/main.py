from aiogram import Dispatcher
from aiogram_dialog.api.entities import DIALOG_EVENT_NAME

from includes.fluent import get_fluent_localization
from middlewares.drop_nothing import DropEmptyCallbackMiddleware
from middlewares.localization import L10nMw
from middlewares.logging import LoggingMw

L10N_FORMAT_KEY = "l10n"
LOGGING_KEY = "log"


def register_middlewares(dp: Dispatcher):
    # Localization (first for use in other Mw)
    locale = get_fluent_localization()
    l10n_mw = L10nMw(locale, L10N_FORMAT_KEY)
    dp.message.outer_middleware(l10n_mw)
    dp.callback_query.outer_middleware(l10n_mw)

    # Drop callback data with only space symbol
    dp.callback_query.outer_middleware(DropEmptyCallbackMiddleware())

    # Logging handlers
    logging_mw = LoggingMw(LOGGING_KEY)
    dp.message.middleware(logging_mw)
    dp.callback_query.middleware(logging_mw)


def register_dialog_update_middlewares(dp: Dispatcher):
    """Те же l10n и log для фоновых обновлений диалогов (``BgManager``, например автоскрытие конфига).

    Такие обновления идут своим событием ``aiogd_update``, а не message/callback_query, и без этого
    геттеры окон падают без ``l10n``. Наблюдатель события появляется только в ``setup_dialogs``,
    поэтому вызывать - после него.
    """
    dp.observers[DIALOG_EVENT_NAME].outer_middleware(L10nMw(get_fluent_localization(), L10N_FORMAT_KEY))
    dp.observers[DIALOG_EVENT_NAME].middleware(LoggingMw(LOGGING_KEY))
