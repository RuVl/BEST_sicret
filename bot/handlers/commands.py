from aiogram import Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from fluent.runtime import FluentLocalization
from structlog import getLogger
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.member import find_member_by_username
from database.methods.person import get_or_create_person, set_lbg_member
from state_machines import CreateByApplyEquipment
from state_machines.inventory import ViewInventory
from state_machines.refund import CreateRefundApply
from state_machines.templates import CreateByTemplate

router = Router()
logger: FilteringBoundLogger = getLogger("commands")


@router.message(CommandStart())
async def start(msg: Message, l10n: FluentLocalization, dialog_manager: DialogManager):
    await msg.answer(l10n.format_value("start-msg"))

    # get-or-create Person и тихая авто-привязка к LbgMember по Telegram-username.
    user = msg.from_user
    if user is not None:
        async with async_session() as session:
            person = await get_or_create_person(session, user.id, user.full_name, user.username)

            if person.lbg_member_id is None and user.username:
                member = await find_member_by_username(session, user.username)
                if member is not None:
                    await set_lbg_member(session, person, member.id)
                    await logger.ainfo(
                        "Person linked to LbgMember",
                        telegram_id=user.id,
                        username=user.username,
                        lbg_member_id=member.id,
                    )

            await session.commit()

    await dialog_manager.reset_stack()


@router.message(Command("create_document"))
async def choose_template(msg: Message, dialog_manager: DialogManager):
    """Ask for a template for creation"""
    await dialog_manager.start(
        CreateByTemplate.CHOOSE_TEMPLATE,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(Command("refund"))
async def start_refund(msg: Message, dialog_manager: DialogManager):
    await dialog_manager.start(
        CreateRefundApply.VIEW,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(Command("create_equipment_apply"))
async def choose_apply_equipment(msg: Message, dialog_manager: DialogManager):
    await dialog_manager.start(
        CreateByApplyEquipment.VIEW,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )


@router.message(Command("inventory"))
async def view_inventory(msg: Message, dialog_manager: DialogManager):
    await dialog_manager.start(
        ViewInventory.SELECT_CATEGORY,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
