from typing import Any

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Back, Button, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Const, Format, Multi
from fluent.runtime import FluentLocalization

from database.main import async_session
from database.methods.category import get_categories
from database.methods.item import get_items_by_category_id
from env import TelegramKeys
from includes import load_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines import CreateByApplyEquipment
from utils import escape_mdv2, L10nFormat

DIALOG_SCHEMA = "equipments/apply_equipment.json"


# ========== Getters ==========
async def get_main_data(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context: BaseContext = dialog_manager.dialog_data.get("context")

    if context is None:
        try:
            schema = load_schema(DIALOG_SCHEMA)
            context = create_context(schema)
            dialog_manager.dialog_data.update(context=context)
        except FileNotFoundError:
            return {
                "view": l10n.format_value("apply-equipment-schema-not-found"),
                "data_kb": [],
                "action_kb": [],
                "can_submit": False,
                "added_items": [],
            }

    custom_items = dialog_manager.dialog_data.get("custom_items", {})
    added_items = [
        (name, f"❌ {name}: {data['quantity']} {data['unit']}")
        for name, data in custom_items.items()
    ]

    custom_items_view = ""
    if custom_items:
        rows = [
            f"\\- {escape_mdv2(name)}: {item_data['quantity']} {escape_mdv2(item_data['unit'])}"
            for name, item_data in custom_items.items()
        ]
        custom_items_view = (
            "\n\n" + l10n.format_value("chose-category") + "\n" + "\n".join(rows)
        )

    return {
        "view": context.render_view(l10n) + custom_items_view,
        "data_kb": context.render_data_kb(l10n),
        "action_kb": context.render_action_kb(l10n),
        "can_submit": context.can_generate() and bool(custom_items),
        "added_items": added_items,
    }


async def get_categories_data(**kwargs) -> dict[str, Any]:
    async with async_session() as session:
        categories = await get_categories(session)

    category_buttons = [(cat.name, str(cat.id)) for cat in categories]
    return {
        "categories": category_buttons,
    }


async def get_items_data(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    cat_id = int(dialog_manager.dialog_data.get("selected_category_id"))
    async with async_session() as session:
        items = await get_items_by_category_id(session, cat_id)

    item_details = {
        item.id: {"name": item.name, "available": item.count, "unit": item.unit}
        for item in items
    }
    dialog_manager.dialog_data["item_details"] = item_details

    return {
        "items": [(item.name, str(item.id)) for item in items],
    }


async def get_quantity_data(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    name = dialog_manager.dialog_data.get("selected_item_name", "предмет")
    unit = dialog_manager.dialog_data.get("item_unit", "шт")
    available = dialog_manager.dialog_data.get("available_count", 0)

    question = l10n.format_value(
        "enter-count-prompt",
        args={
            "name": escape_mdv2(name),
            "unit": escape_mdv2(unit),
            "available": available,
        },
    )

    return {
        "question": question,
    }


async def get_property_data(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context: PrimitiveContext = dialog_manager.dialog_data.get("context")

    return {
        "question": context.ask_question(),
        "action_kb": context.render_action_kb(l10n),
    }


# ========== Handlers ==========
async def on_property_selected(
    clb: CallbackQuery,
    select: Select,
    dialog_manager: DialogManager,
    field_key: str,
):
    context: BaseContext = dialog_manager.dialog_data.get("context")
    context = context.view(field_key)

    dialog_manager.dialog_data.update(context=context)
    if isinstance(context, PrimitiveContext):
        await dialog_manager.switch_to(CreateByApplyEquipment.INPUT_PROPERTY)
    else:
        await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)


async def on_property_input(
    msg: Message,
    widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    value: str,
):
    context: PrimitiveContext = dialog_manager.dialog_data.get("context")
    try:
        parsed_value = context.parse(value)
    except ValueError as e:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await msg.answer(l10n.format_value(str(e)))
        return

    context.set_value(parsed_value)
    try:
        context = context.do("back")
        dialog_manager.dialog_data.update(context=context)
    except ValueError:
        pass

    await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)


async def on_category_selected(
    clb: CallbackQuery,
    select: Select,
    dialog_manager: DialogManager,
    category_id: str,
):
    dialog_manager.dialog_data["selected_category_id"] = category_id
    await dialog_manager.switch_to(CreateByApplyEquipment.SELECT_ITEM)


async def on_item_selected(
    clb: CallbackQuery,
    select: Select,
    dialog_manager: DialogManager,
    item_id: str,
):
    item_id_int = int(item_id)
    details = dialog_manager.dialog_data.get("item_details", {}).get(item_id_int)

    if not details:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await clb.answer(l10n.format_value("category-empty"), show_alert=True)
        return

    dialog_manager.dialog_data.update(
        selected_item_id=item_id_int,
        selected_item_name=details["name"],
        available_count=details["available"],
        item_unit=details["unit"],
    )
    await dialog_manager.switch_to(CreateByApplyEquipment.INPUT_QUANTITY)


async def on_quantity_input(
    msg: Message,
    widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    value: str,
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    try:
        count = int(value)
        if count <= 0:
            raise ValueError
    except ValueError:
        await msg.answer(l10n.format_value("invalid-positive-number"))
        return

    available = dialog_manager.dialog_data.get("available_count", 0)
    name = dialog_manager.dialog_data.get("selected_item_name")
    unit = dialog_manager.dialog_data.get("item_unit")

    if count > available:
        await msg.answer(
            l10n.format_value(
                "count-exceeds-available",
                args={
                    "name": name,
                    "available": available,
                    "unit": unit,
                    "requested": count,
                },
            ),
        )
        return

    custom_items = dialog_manager.dialog_data.setdefault("custom_items", {})
    custom_items[name] = {
        "quantity": count,
        "unit": unit,
    }

    # Clean up item selection data
    for key in (
        "selected_category_id",
        "selected_item_id",
        "selected_item_name",
        "available_count",
        "item_unit",
        "item_details",
    ):
        dialog_manager.dialog_data.pop(key, None)

    await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)


async def on_delete_item(
    clb: CallbackQuery,
    select: Select,
    dialog_manager: DialogManager,
    item_name: str,
):
    custom_items = dialog_manager.dialog_data.get("custom_items", {})
    if item_name in custom_items:
        del custom_items[item_name]
        dialog_manager.dialog_data["custom_items"] = custom_items
    await clb.answer()


async def on_action_selected(
    clb: CallbackQuery,
    select: Select,
    dialog_manager: DialogManager,
    action: str,
):
    context: BaseContext = dialog_manager.dialog_data.get("context")
    context = context.do(action)
    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(CreateByApplyEquipment.VIEW)


async def on_submit(clb: CallbackQuery, widget: Button, dialog_manager: DialogManager):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context: BaseContext = dialog_manager.dialog_data.get("context")

    schema = load_schema(DIALOG_SCHEMA)
    data = context.generate_context()

    success, error_msg = validate_data(schema, data)
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return

    if TelegramKeys.TREASURER_ID:
        await clb.bot.send_message(
            TelegramKeys.TREASURER_ID,
            l10n.format_value(
                "equipment-chosen",
                args={"by_username": escape_mdv2(clb.from_user.username)},
            ),
        )
        await clb.message.forward(TelegramKeys.TREASURER_ID)
        await clb.answer(l10n.format_value("application-saved"), show_alert=True)
    else:
        await clb.answer(l10n.format_value("application-error"), show_alert=True)

    await dialog_manager.done()


# ========== Dialog Definition ==========
check_apply_equipment_dialog = Dialog(
    # --- VIEW Window ---
    Window(
        Multi(
            Format("{view}\n"),
            L10nFormat("required-hint"),
        ),
        # Form fields editing
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="prop_edit",
                item_id_getter=lambda x: x[1],
                items="data_kb",
                on_click=on_property_selected,
            ),
            id="prop_scroll",
            width=2,
            height=3,
            hide_on_single_page=True,
        ),
        # Added items deletion
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="item_delete",
                item_id_getter=lambda x: x[0],
                items="added_items",
                on_click=on_delete_item,
            ),
            id="added_items_scroll",
            width=2,
            height=3,
            hide_on_single_page=True,
            when=F["added_items"],
        ),
        # Navigation to item selection
        SwitchTo(
            Const("➕ Добавить предмет"),
            id="go_to_categories",
            state=CreateByApplyEquipment.SELECT_CATEGORY,
        ),
        # Form actions (Submit/Cancel etc)
        Select(
            Format("{item[0]}"),
            id="form_action",
            item_id_getter=lambda x: x[1],
            items="action_kb",
            on_click=on_action_selected,
        ),
        # Final submit
        Button(
            L10nFormat("submit-application"),
            id="submit_app",
            on_click=on_submit,
            when=F["can_submit"],
        ),
        getter=get_main_data,
        state=CreateByApplyEquipment.VIEW,
    ),
    # --- INPUT PROPERTY Window ---
    Window(
        Format("{question}"),
        TextInput(id="prop_input", on_success=on_property_input),
        Select(
            Format("{item[0]}"),
            id="prop_action",
            item_id_getter=lambda x: x[1],
            items="action_kb",
            on_click=on_action_selected,
        ),
        getter=get_property_data,
        state=CreateByApplyEquipment.INPUT_PROPERTY,
    ),
    # --- SELECT CATEGORY Window ---
    Window(
        L10nFormat("choose-category"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="cat_select",
                item_id_getter=lambda x: x[1],
                items="categories",
                on_click=on_category_selected,
            ),
            id="cat_scroll",
            width=2,
            height=5,
            hide_on_single_page=True,
        ),
        SwitchTo(L10nFormat("back"), "back", CreateByApplyEquipment.VIEW),
        getter=get_categories_data,
        state=CreateByApplyEquipment.SELECT_CATEGORY,
    ),
    # --- SELECT ITEM Window ---
    Window(
        L10nFormat("select-item-prompt"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="item_select",
                item_id_getter=lambda x: x[1],
                items="items",
                on_click=on_item_selected,
            ),
            id="items_scroll",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        Back(L10nFormat("back")),
        getter=get_items_data,
        state=CreateByApplyEquipment.SELECT_ITEM,
    ),
    # --- INPUT QUANTITY Window ---
    Window(
        Format("{question}"),
        TextInput(id="qty_input", on_success=on_quantity_input),
        Back(L10nFormat("back")),
        getter=get_quantity_data,
        state=CreateByApplyEquipment.INPUT_QUANTITY,
    ),
)
