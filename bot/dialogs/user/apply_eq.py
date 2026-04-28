from typing import Any

from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Button, Next, Back, SwitchTo
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.text import Format, Multi, Const
from aiogram import F
from aiogram_dialog.widgets.input import TextInput
from sqlalchemy.ext.asyncio import AsyncSession
from fluent.runtime import FluentLocalization
from middlewares import L10N_FORMAT_KEY

from database.methods.category import get_categories
from database.methods.item import get_items_by_categories_id
from env import TelegramKeys
from state_machines import CreateByApplyEquipment
from includes.equipment import load_schema, validate_data
from includes.equipment import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from utils import L10nFormat, escape_mdv2

DIALOG_SCHEMA = "apply_equipment"

# для окна просмотра
async def get_equipment_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    session: AsyncSession = dialog_manager.middleware_data.get("db_session")
    context: BaseContext = dialog_manager.dialog_data.get('context')

    categories = await get_categories(session)
    categories_kb = [(cat.name, str(cat.id)) for cat in categories]

    if context is None:
        form_id = dialog_manager.dialog_data.get('form_id', DIALOG_SCHEMA)
        try:
            schema = load_schema(form_id)
            context = create_context(schema)
            dialog_manager.dialog_data.update(form_id=form_id, context=context)
        except FileNotFoundError:
            return {
                'view': l10n.format_value('welcome-error-schema-equipment'),
                'data_kb': [],
                'action_kb': [],
                'categories_kb': categories_kb,
                'can_submit': False,
            }

    custom_items = dialog_manager.dialog_data.get("custom_items", {})
    custom_items_view = ""
    if custom_items:
        rows = [
            f"\\- {escape_mdv2(name)}: {item_data['quantity']} {escape_mdv2(item_data['unit'])}"
            for name, item_data in custom_items.items()
        ]
        custom_items_view = l10n.format_value('chose_category') + "\n".join(rows)

    return {
        'view': context.render_view(l10n) + custom_items_view,
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


async def on_add_input(msg: Message, text_input: TextInput, dialog_manager: DialogManager, value: str):
    mode = dialog_manager.dialog_data.get("input_mode", "form_property")
    if mode == "item_quantity":
        await on_count_success(msg, text_input, dialog_manager, value)
        return
    await set_property(msg, text_input, dialog_manager, value)


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

    dialog_manager.dialog_data.update(apply_equipment=apply_equipment_data_person, context=context)
    await dialog_manager.switch_to(CreateByApplyEquipment.ADD if isinstance(context, PrimitiveContext) else CreateByApplyEquipment.VIEW)


# for categoriya
async def on_category_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, callback_id: str):
    cat_id = int(callback_id)
    session = dialog_manager.middleware_data.get("db_session")
    items = await get_items_by_categories_id(session, cat_id)
    items_kb = [(item.name, f"item_{item.id}") for item in items]

    item_details = {
        item.id: {"name": item.name, "available": item.count, "unit": item.unit}
        for item in items
    }

    dialog_manager.dialog_data.update(
        input_mode="category_items",
        selected_category_id=cat_id,
        items_kb=items_kb,
        item_details=item_details
    )
    await dialog_manager.switch_to(CreateByApplyEquipment.ADD)


# for edit the field
async def on_data_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, field_key: str):
    context: BaseContext = dialog_manager.dialog_data.get('context')
    context = context.view(field_key)
    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(
        CreateByApplyEquipment.ADD if isinstance(context, PrimitiveContext)
        else CreateByApplyEquipment.VIEW
    )


# base buttons
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
    # Send notification to treasurer if exists
    if TelegramKeys.TREASURER_ID:
        await clb.bot.send_message(
            TelegramKeys.TREASURER_ID,
            l10n.format_value('equipment-chosen', args={
                'by_username': escape_mdv2(clb.from_user.username)})
        )
        await clb.message.forward(TelegramKeys.TREASURER_ID)
        await clb.answer(l10n.format_value('application-saved'), show_alert=True)
    await clb.answer(l10n.format_value('application-error'), show_alert=True)
    await dialog_manager.done()


async def on_item_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, callback_id: str):
    item_id = int(callback_id.replace("item_", ""))
    details = dialog_manager.dialog_data["item_details"].get(item_id)

    if not details:
        l10n = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await clb.answer(l10n.format_value('category-empty'), show_alert=True)
        return

    dialog_manager.dialog_data.update(
        input_mode="item_quantity",
        selected_item_id=item_id,
        selected_item_name=details["name"],
        available_count=details["available"],
        item_unit=details["unit"]
    )
    await dialog_manager.switch_to(CreateByApplyEquipment.ADD)


async def get_add_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    mode = dialog_manager.dialog_data.get("input_mode", "form_property")
    context = dialog_manager.dialog_data.get("context")

    if mode == "category_items":
        return {
            "question": l10n.format_value("select-item-prompt"),
            "input_mode": mode,
            "items_kb": dialog_manager.dialog_data.get("items_kb", []),
            "action_kb": []
        }

    elif mode == "item_quantity":
        name = escape_mdv2(dialog_manager.dialog_data.get("selected_item_name", "предмет"))
        unit = escape_mdv2(dialog_manager.dialog_data.get("item_unit", "шт"))
        available = dialog_manager.dialog_data.get("available_count", 0)

        return {
            "question": l10n.format_value("enter-count-prompt", args={
                "name": name, "unit": unit, "available": available
            }),
            "input_mode": mode,
            "items_kb": [],
            "action_kb": []
        }

    else:  # form_property
        return {
            "question": context.ask_question() if context else "",
            "input_mode": mode,
            "items_kb": [],
            "action_kb": context.render_action_kb(l10n) if context else []
        }


async def on_count_success(msg: Message, _: TextInput, dialog_manager: DialogManager, value: str):
    l10n = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    try:
        count = int(value)
        if count <= 0: raise ValueError
    except ValueError:
        await msg.answer(l10n.format_value("invalid-positive-number"))
        return

    item_id = dialog_manager.dialog_data.get("selected_item_id")
    all_items_details = dialog_manager.dialog_data.get("item_details", {})
    current_item = all_items_details.get(item_id, {})

    available = current_item.get("available", 0)
    unit = current_item.get("unit", "шт")
    name = current_item.get("name", "предмет")

    if count > available:
        await msg.answer(l10n.format_value("count-exceeds-available", args={
            "name": name, "available": available, "unit": unit, "requested": count
        }))
        return

    dialog_manager.dialog_data.setdefault("custom_items", {})[name] = {
        "quantity": count,
        "unit": unit
    }

    for key in ("selected_category_id", "selected_item_id", "selected_item_name", "available_count", "item_unit", "item_details", "items_kb"):
        dialog_manager.dialog_data.pop(key, None)
    dialog_manager.dialog_data.update(input_mode="form_property")

    await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)


check_apply_equipment_dialog = Dialog(
    Window(  # Окно с заявкой
        Multi(
            Format('{view}\n\n'),
            Const(r'_\* \- _'),
            L10nFormat('required-hint'),
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
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='item_select',
                item_id_getter=lambda x: x[1],
                items='items_kb',
                on_click=on_item_selected
            ),
            id='items_scroll',
            width=2,
            height=5,
            hide_on_single_page=True,
            when=F["input_mode"] == "category_items"
        ),
        TextInput(
            'input_property',
            on_success=on_add_input,
        ),
        Select(
            Format('{item[0]}'),
            id='equipment_action',
            item_id_getter=lambda x: x[1],
            items='action_kb',
            on_click=on_action_selected,
            when=F["input_mode"] == "form_property"
        ),
        getter=get_add_context,
        state=CreateByApplyEquipment.ADD,
        preview_add_transitions=[Back()]
    )

)
