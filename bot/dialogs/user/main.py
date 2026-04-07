from aiogram import Router

from dialogs.user.templates import template_dialog
from dialogs.user.inventory import inventory_dialog 

user_dialog_router = Router()
user_dialog_router.include_routers(
    template_dialog,
    inventory_dialog,
)
