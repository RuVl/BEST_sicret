from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode, ShowMode
from fluent.runtime import FluentLocalization

from state_machines.templates import CreateByTemplate

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
