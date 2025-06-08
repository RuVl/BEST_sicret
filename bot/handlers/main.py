from aiogram import Dispatcher, Router

from dialogs import register_dialogs
from handlers import commands


def register_handlers(dp: Dispatcher):
	"""
	Register all routers here.
	WARNING: order is important: only the first suitable handler will start.
	"""

	# Register aiogram-dialogs on new router
	dialogs_router = Router()
	register_dialogs(dp, dialogs_router)

	dp.include_routers(
		commands.router,
		dialogs_router  # needs to be last
	)
