from aiogram import Router

from dialogs.user.apply_eq import check_apply_equipment_dialog
from dialogs.user.refund import refund_dialog
from dialogs.user.templates import template_dialog

user_dialog_router = Router()
user_dialog_router.include_routers(
    template_dialog,
    refund_dialog,
    check_apply_equipment_dialog,
)
