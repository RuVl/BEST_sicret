from aiogram import Router

from dialogs.user.apply_eq import apply_equipment_dialog
from dialogs.user.inventory import inventory_dialog
from dialogs.user.profile import profile_dialog
from dialogs.user.refund import refund_dialog
from dialogs.user.templates import template_dialog
from dialogs.user.vpn import vpn_dialog

user_dialog_router = Router()
user_dialog_router.include_routers(
    profile_dialog,
    template_dialog,
    refund_dialog,
    apply_equipment_dialog,
    inventory_dialog,
    vpn_dialog,
)
