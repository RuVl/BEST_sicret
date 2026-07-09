from aiogram import Router

from dialogs.user.apply_eq import apply_equipment_dialog
from dialogs.user.refund import refund_dialog
from dialogs.user.inventory import inventory_dialog
from dialogs.user.templates import template_dialog
from dialogs.user import add_eq
from dialogs.user import create_category

user_dialog_router = Router()
user_dialog_router.include_routers(
    template_dialog,
    refund_dialog,
    apply_equipment_dialog,
    inventory_dialog,
    add_eq.dialog, 
    create_category.dialog
)
