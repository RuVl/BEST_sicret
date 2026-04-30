from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode, ShowMode
from fluent.runtime import FluentLocalization

from state_machines.refund import CreateRefundApply
from state_machines.templates import CreateByTemplate
from state_machines import CreateByApplyEquipment

router = Router()


@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization, dialog_manager: DialogManager):
    await msg.answer(l10n.format_value("start-msg"))
    await dialog_manager.reset_stack()


@router.message(Command("create_document"))
async def choose_template(msg: Message, dialog_manager: DialogManager):
    """Ask for a template for creation"""
    await dialog_manager.start(
        CreateByTemplate.CHOOSE_TEMPLATE,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(Command("requisites_apply"))
async def start_refund(msg: Message, dialog_manager: DialogManager):
    await dialog_manager.start(
        CreateRefundApply.VIEW,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(Command("create_equipment_apply"))
async def choose_apply_equipment(_: Message, dialog_manager: DialogManager):
    await dialog_manager.start(
        CreateByApplyEquipment.VIEW,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
