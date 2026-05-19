import logging

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Button
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession

from database.methods.category import create_category
from middlewares import L10N_FORMAT_KEY, DB_SESSION_KEY
from state_machines import CategoryCreate
from utils import L10nFormat, escape_mdv2

logger = logging.getLogger(__name__)


async def on_cancel(
    _clb: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager
):
    await dialog_manager.done(result={})


async def on_category_name_input(
    msg: Message,
    _: TextInput,
    dialog_manager: DialogManager,
    text: str
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    session: AsyncSession = dialog_manager.middleware_data.get(DB_SESSION_KEY)

    if session is None:
        await msg.answer(escape_mdv2(l10n.format_value('database-error')))
        return

    try:
        category = await create_category(session, name=text)

        await msg.answer(
            escape_mdv2(l10n.format_value('category-created', args={
                'name': category.name
            }))
        )

        await dialog_manager.done(result={
            'category_id': category.id,
            'category_name': category.name,
        })

    except Exception:
        logger.exception("Error creating category '%s'", text)
        await msg.answer(escape_mdv2(l10n.format_value('category-error')))


dialog = Dialog(
    Window(
        L10nFormat('category-name-prompt'),
        TextInput('category_name_input', on_success=on_category_name_input),
        Button(
            L10nFormat('back-button'),
            id='cancel_create_category',
            on_click=on_cancel,
        ),
        state=CategoryCreate.INPUT_NAME,
    )
)