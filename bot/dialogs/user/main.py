from aiogram import Router

from dialogs.user.templates import template_dialog
from dialogs.user.apply_eq import check_apply_equipment_dialog
from dialogs.user import add_eq
from dialogs.user import create_category

user_dialog_router = Router()
user_dialog_router.include_routers(
    template_dialog,
    check_apply_equipment_dialog,
    add_eq.dialog, 
    create_category.dialog
)
