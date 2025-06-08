from aiogram import Dispatcher

from includes.fluent import get_fluent_localization
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from middlewares.drop_nothing import DropEmptyCallbackMiddleware
from middlewares.localization import L10nMw
from middlewares.logging import LoggingMw


def register_middlewares(dp: Dispatcher):
	# Drop callback data with only space symbol
	dp.callback_query.outer_middleware(DropEmptyCallbackMiddleware())

	# Localization
	locale = get_fluent_localization()
	l10n_mw = L10nMw(locale, L10N_FORMAT_KEY)
	dp.message.outer_middleware(l10n_mw)
	dp.callback_query.outer_middleware(l10n_mw)

	# Logging handlers
	logging_mw = LoggingMw(LOGGING_KEY)
	dp.message.middleware(logging_mw)
	dp.callback_query.middleware(logging_mw)
