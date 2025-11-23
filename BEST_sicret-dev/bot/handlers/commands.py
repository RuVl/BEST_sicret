from typing import Dict, Any

from aiogram import Router
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram_dialog import DialogManager, StartMode, ShowMode
from fluent.runtime import FluentLocalization

from database.methods.person import get_person_by_telegram_id, create_person
from filters import get_session
from state_machines.templates import CreateByTemplate
from state_machines.property_database import PropertyDatabase
from state_machines.request_refund import RequestRefund

router = Router()


@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization, data: Dict[str, Any]):
    session = get_session(data)
    person = await get_person_by_telegram_id(session, msg.from_user.id)
    if person is None:
        full_name = msg.from_user.full_name or f"{msg.from_user.first_name or ''} {msg.from_user.last_name or ''}".strip() or "User"
        person = await create_person(
            session=session,
            telegram_id=msg.from_user.id,
            full_name=full_name,
        )
    await msg.answer(f'Hello, {person.full_name}')


@router.message(Command('create_document'))
async def choose_template(_: Message, dialog_manager: DialogManager):
    """ Ask for a template for creation """
    await dialog_manager.start(
        CreateByTemplate.CHOOSE_TEMPLATE,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND
    )


@router.message(Command('property_database'))
async def property_database(_: Message, dialog_manager: DialogManager):
    """ Запуск диалога базы имущества """
    await dialog_manager.start(
        PropertyDatabase.MAIN_MENU,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND
    )


@router.message(Command('request_refund'))
async def request_refund(_: Message, dialog_manager: DialogManager):
    """ Запуск диалога запроса рефанда """
    # Инициализируем данные формы
    dialog_manager.dialog_data.update(
        name=None,
        event=None,
        reason=None,
        amount=None,
        card_number=None
    )
    await dialog_manager.start(
        RequestRefund.MAIN_FORM,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND
    )
