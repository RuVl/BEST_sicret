"""Единственная команда бота - ``/start``.

Всё остальное открывается кнопками главного меню: доступ к приказам, заявкам и имуществу
есть только у состоящих в LBG, а команда такую проверку обойти не даёт.
"""

from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message
from aiogram_dialog import DialogManager, ShowMode, StartMode
from structlog import getLogger
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.member import find_member_by_username
from database.methods.person import get_or_create_person, set_lbg_member
from state_machines.profile import ViewProfile

router = Router()
logger: FilteringBoundLogger = getLogger("commands")


@router.message(CommandStart())
async def start(msg: Message, dialog_manager: DialogManager):
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

    await dialog_manager.start(
        ViewProfile.VIEW,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND,
    )
