from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode, ShowMode
from fluent.runtime import FluentLocalization

from state_machines.templates import CreateByTemplate
from state_machines import CreateByApplyEquipment
from state_machines import EquipmentAdd
from env import TelegramKeys

router = Router()


@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization):
    await msg.answer(l10n.format_value("start-msg"))


@router.message(Command('create_document'))
async def choose_template(_: Message, dialog_manager: DialogManager):
    """ Ask for a template for creation """
    await dialog_manager.start(
        CreateByTemplate.CHOOSE_TEMPLATE,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND
    )


@router.message(Command('create_equipment_apply'))
async def choose_apply_equipment(_: Message, dialog_manager: DialogManager):
    await dialog_manager.start(
        CreateByApplyEquipment.VIEW,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND
    )


@router.message(Command("add_equipment"), F.user.id == TelegramKeys.TREASURER_ID)
async def choose_add_equipment(_: Message, dialog_manager: DialogManager):
    await dialog_manager.start(EquipmentAdd.START, mode=StartMode.RESET_STACK)


@router.message(Command("add_equipment"))
async def cmd_add_equipment_denied(message: Message, l10n: FluentLocalization):
    await message.answer(l10n.format_value("foreign-person"))
