from aiogram import Dispatcher, Router
from aiogram_dialog import setup_dialogs
from aiogram_dialog.tools import render_transitions

from dialogs.user import user_dialog_router
from env import ProjectKeys


def register_dialogs(dp: Dispatcher, router: Router):
	router.include_routers(
		user_dialog_router
	)

	# Render dialogs preview
	if ProjectKeys.DEBUG:
		render_transitions(router)

	setup_dialogs(dp)  # Register on dispatcher for using anywhere
