from aiogram import Router

from dialogs.user.property_database import property_database_dialog
from dialogs.user.request_refund import request_refund_dialog
from dialogs.user.templates import template_dialog
from dialogs.user.staff_db import staff_db_dialog

user_dialog_router = Router()
user_dialog_router.include_routers(
    template_dialog,
    staff_db_dialog,
    property_database_dialog,
    request_refund_dialog
)
