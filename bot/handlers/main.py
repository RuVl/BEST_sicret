from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from fluent.runtime import FluentLocalization

router = Router()

@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization):
    await msg.answer(l10n.format_value("start-msg"))
