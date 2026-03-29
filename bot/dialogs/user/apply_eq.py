from aiogram_dialog import Dialog, Window
from state_machines import CreateByApplyEquipment
from utils import L10nFormat

async def get_equipment(dialog_manager, **kwargs):
    return {}

check_apply_equipment_dialog = Dialog(
    Window(  # Окно с заявкой
        L10nFormat('choose-apply-equipment'),
        state=CreateByApplyEquipment.CHOOSE_APPLY_EQUIPMENT,
        getter=get_equipment
    )
)