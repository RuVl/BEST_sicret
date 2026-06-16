from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Button, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.text import Format, Multi
from fluent.runtime import FluentLocalization

from env import settings
from includes import load_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines import CreateByApplyEquipment, ViewInventory
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
async def on_start_add_item(clb: CallbackQuery, button: Button, manager: DialogManager):
    await manager.start(
        ViewInventory.SELECT_CATEGORY,
        data={"selection_mode": True},
    )


async def on_inventory_result(start_data: Any, result: Any, manager: DialogManager):
    if not result:
        return

    manager.dialog_data.update(
        selected_item_id=result["item_id"],
        selected_item_name=result["name"],
        available_count=result["count"],
        item_unit=result["unit"],
    )
    await manager.switch_to(CreateByApplyEquipment.INPUT_QUANTITY)


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
        "selected_item_id",
        "selected_item_name",
        "available_count",
        "item_unit",
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

    if settings.telegram.TREASURER_ID:
        await clb.bot.send_message(
            settings.telegram.TREASURER_ID,
            l10n.format_value(
                "equipment-chosen",
                args={"by_username": escape_mdv2(clb.from_user.username)},
            ),
        )
        await clb.message.forward(settings.telegram.TREASURER_ID)
        await clb.answer(l10n.format_value("application-saved"), show_alert=True)
    else:
        await clb.answer(l10n.format_value("application-error"), show_alert=True)

    await dialog_manager.done()


# ========== Dialog Definition ==========
apply_equipment_dialog = Dialog(
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
            when="added_items",
        ),
        # Navigation to item selection
        Button(
            L10nFormat("apply-eq-add-item"),
            id="go_to_inventory",
            on_click=on_start_add_item,
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
            when="can_submit",
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
    # --- INPUT QUANTITY Window ---
    Window(
        Format("{question}"),
        TextInput(id="qty_input", on_success=on_quantity_input),
        SwitchTo(
            L10nFormat("back"),
            id="back_to_view",
            state=CreateByApplyEquipment.VIEW,
        ),
        getter=get_quantity_data,
        state=CreateByApplyEquipment.INPUT_QUANTITY,
    ),
    on_process_result=on_inventory_result,
)
