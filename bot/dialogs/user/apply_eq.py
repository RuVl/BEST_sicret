from typing import Any

from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Url, Button, Next, Back, SwitchTo
from aiogram.types import CallbackQuery, BufferedInputFile, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.text import Format, Multi, Const
from aiogram import F
from aiogram_dialog.widgets.input import TextInput
from sqlalchemy.ext.asyncio import AsyncSession
from fluent.runtime import FluentLocalization
from middlewares import L10N_FORMAT_KEY

from database.methods.category import get_categories
from env import TelegramKeys
from state_machines import CreateByApplyEquipment
from includes.equipment import load_schema, validate_data
from includes.equipment import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from utils import L10nFormat, escape_mdv2



# для окна просмотра
async def get_equipment_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    session: AsyncSession = dialog_manager.middleware_data.get("db_session")
    context: BaseContext = dialog_manager.dialog_data.get('context')

    if "categories_kb" not in dialog_manager.dialog_data:
        categories = await get_categories(session)
        dialog_manager.dialog_data["categories_kb"] = [
            (cat.name, f"cat_{cat.id}") for cat in categories
        ]
    categories_kb = dialog_manager.dialog_data["categories_kb"]

    if context is None:
        form_id = dialog_manager.dialog_data.get('form_id', 'apply_equipment')
        try:
            schema = load_schema(form_id)
            context = create_context(schema)
            dialog_manager.dialog_data.update(form_id=form_id, context=context)
        except FileNotFoundError:
            return {
                'view': l10n.format_value('welcome-select-equipment'),
                'data_kb': [],
                'action_kb': [],
                'categories_kb': categories_kb,
                'can_submit': False,
            }

    return {
        'view': context.render_view(l10n),
        'data_kb': context.render_data_kb(l10n),
        'action_kb': context.render_action_kb(l10n),
        'categories_kb': categories_kb,
        'can_submit': context.can_generate(),
    }

# для окна редактирования

async def get_property_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context: PrimitiveContext = dialog_manager.dialog_data.get('context')
    return {
        'question': context.ask_question(),
        'action_kb': context.render_action_kb(l10n),
    }

# оброботчики
# for json
async def on_form_equipment_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, apply_equipment_data_person: str):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    try:
        schema = load_schema(apply_equipment_data_person)
        context = create_context(schema)
    except FileNotFoundError:
        await clb.answer(l10n.format_value('schema-not-found'), show_alert=True)
        return

    # Send notification to treasurer if exists
    if TelegramKeys.TREASURER_ID:
        await clb.bot.send_message(
            TelegramKeys.TREASURER_ID,
            l10n.format_value('equipment-chosen', args={
                'by_username': escape_mdv2(clb.from_user.username)
            })
        )

    dialog_manager.dialog_data.update(apply_equipment=apply_equipment_data_person, context=context)
    await dialog_manager.switch_to(CreateByApplyEquipment.ADD if isinstance(context, PrimitiveContext) else CreateByApplyEquipment.VIEW)

# for categoriya
async def on_category_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, callback_id: str):
    cat_id = int(callback_id.replace("cat_", ""))
    dialog_manager.dialog_data.update(selected_category_id=cat_id)
    await dialog_manager.show()

# for edit the field
async def on_data_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, field_key: str):
    context: BaseContext = dialog_manager.dialog_data.get('context')
    context = context.view(field_key)
    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(
        CreateByApplyEquipment.ADD if isinstance(context, PrimitiveContext)
        else CreateByApplyEquipment.VIEW
    )

# base buttons like nazad, dalee, otmena
async def on_action_selected(_clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, action: str):
    context: BaseContext = dialog_manager.dialog_data.get('context')
    context = context.do(action)

    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)

# processing user input
async def set_property(msg: Message, _: TextInput, dialog_manager: DialogManager, value: str):
    context: PrimitiveContext = dialog_manager.dialog_data.get('context')
    try:
        parsed_value = context.parse(value)
    except ValueError as e:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await msg.answer(l10n.format_value(str(e)))
        return

    context.set_value(parsed_value)
    try:  # try to go back
        context = context.do('back')
    except ValueError:
        await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)
        return

    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)

# save data

async def on_submit(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    form_id: str = dialog_manager.dialog_data.get('form_id')
    context: BaseContext = dialog_manager.dialog_data.get('context')
    data = context.generate_context()
    schema = load_schema(form_id)

    success, error_msg = validate_data(schema, data)
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return
    await clb.answer(l10n.format_value('application-saved'), show_alert=True)
    await dialog_manager.done()

check_apply_equipment_dialog = Dialog(
    Window(  # Окно с заявкой
        Multi(
            Format('{view}\n\n'),
            Const(r'_\* \- '),
            L10nFormat('required-hint'),
            Const('_'),
            sep=''
        ),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='category_select',
                item_id_getter=lambda x: x[1],
                items='categories_kb',
                on_click=on_category_selected
            ),
            id='category_scroll',
            width=2,
            height=5,
            hide_on_single_page=True
        ),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='equipment_change',
                item_id_getter=lambda x: x[1],
                items='data_kb',
                on_click=on_data_selected
            ),
            id='form_scroll',
            width=2,
            height=5,
            hide_on_single_page=True
        ),
        Select(
            Format('{item[0]}'),
            id='equipment_action',
            item_id_getter=lambda x: x[1],
            items='action_kb',
            on_click=on_action_selected
        ),

        Row(Button(
            L10nFormat('submit-application'),
            id='submit_application',
            on_click=on_submit,
            when=F['can_submit']
        )),
        getter=get_equipment_context,
        state=CreateByApplyEquipment.VIEW,
        preview_add_transitions=[
            SwitchTo('', '', CreateByApplyEquipment.VIEW),
            Next()
        ]
    ),
    Window(  # Окно редактирования
        Format('{question}'),
        TextInput('input_property', on_success=set_property),
        Select(
            Format('{item[0]}'),
            id='equipment_action',
            item_id_getter=lambda x: x[1],
            items='action_kb',
            on_click=on_action_selected
        ),
        getter=get_property_context,
        state=CreateByApplyEquipment.ADD,
        preview_add_transitions=[Back()]
    )
)