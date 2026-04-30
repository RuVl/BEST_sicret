from typing import Any

from aiogram import F
from aiogram.enums import ButtonStyle, ContentType
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, Row, ScrollingGroup, Select
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from env import ProjectKeys
from includes import load_schema
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines import CreateRefundApply
from utils import L10nFormat


# ========== Окно просмотра ==========
async def create_refund_apply(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    **kwargs,
) -> dict[str, Any]:
    ctx: BaseContext = dialog_manager.dialog_data.get("ctx")

    if ctx is None:
        try:
            schema = load_schema("refunds/apply.json")
            ctx = create_context(schema)
            dialog_manager.dialog_data.update(ctx=ctx)
        except FileNotFoundError as e:
            await log.aexception("Failed to load refunds jsonschema", exc_info=e)
            return {
                "view": l10n.format_value("refund-schema-not-found"),
                "data_kb": [],
                "action_kb": [],
                "can_send": False,
            }

    bill = dialog_manager.dialog_data.get("bill")

    return {
        "view": ctx.render_view(l10n),
        "data_kb": ctx.render_data_kb(l10n),
        "action_kb": ctx.render_action_kb(l10n),
        "bill": bill,
        "can_send": bill and ctx.can_generate(),
    }


async def on_data_selected(
    clb: CallbackQuery,
    select: Select,
    dialog_manager: DialogManager,
    data: str,
) -> None:
    ctx: BaseContext = dialog_manager.dialog_data.get("ctx")
    ctx = ctx.view(data)

    await clb.answer()
    dialog_manager.dialog_data.update(ctx=ctx)

    if isinstance(ctx, PrimitiveContext):
        await dialog_manager.switch_to(CreateRefundApply.EDIT)
    else:
        await dialog_manager.switch_to(CreateRefundApply.VIEW)


async def send_treasure(
    clb: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    pass


# ========== Окно редактирования ==========
async def get_property_context(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    **kwargs,
) -> dict[str, Any]:
    ctx: BaseContext = dialog_manager.dialog_data.get("ctx")
    return {
        "question": ctx.ask_question(),
        "action_kb": ctx.render_action_kb(l10n),
    }


async def set_property(
    msg: Message,
    widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    value: str,
) -> None:
    ctx: PrimitiveContext = dialog_manager.dialog_data.get("ctx")
    try:
        parsed_value = ctx.parse(value)
    except ValueError as e:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await msg.answer(l10n.format_value(str(e)))
        return

    ctx.set_value(parsed_value)
    ctx = ctx.do(ctx.BACK_ACTION)

    dialog_manager.dialog_data.update(ctx=ctx)
    await dialog_manager.switch_to(CreateRefundApply.VIEW)


async def on_action_selected(
    clb: CallbackQuery,
    select: Select,
    dialog_manager: DialogManager,
    action: str,
):
    ctx: PrimitiveContext = dialog_manager.dialog_data.get("ctx")
    ctx = ctx.do(action)

    dialog_manager.dialog_data.update(ctx=ctx)
    await dialog_manager.switch_to(CreateRefundApply.VIEW)


# ========== Окно добавления чека ==========
async def add_bill(
    msg: Message, widget: MessageInput, dialog_manager: DialogManager
) -> None:
    ProjectKeys.REFUND_BILLS_DIR


refund_dialog = Dialog(
    Window(
        Format("{view}"),
        ScrollingGroup(
            Select(
                Format("{item[0]}"),
                id="apply_change",
                item_id_getter=lambda item: item[1],
                items="data_kb",
                on_click=on_data_selected,
            ),
            id="apply_change_scroll",
            width=2,
            height=5,
            hide_on_single_page=True,
        ),
        Row(
            Button(
                L10nFormat("refund-send"),
                id="send_treasure",
                on_click=send_treasure,
                when=F["can_send"],
                style=Style(style=ButtonStyle.SUCCESS, emoji_id="5388971216629412467"),
            ),
        ),
        getter=create_refund_apply,
        state=CreateRefundApply.VIEW,
    ),
    Window(  # Окно редактирования
        Format("{question}"),
        TextInput("input_property", on_success=set_property),
        Select(
            Format("{item[0]}"),
            id="action",
            item_id_getter=lambda x: x[1],
            items="action_kb",
            on_click=on_action_selected,
        ),
        getter=get_property_context,
        state=CreateRefundApply.EDIT,
    ),
    Window(  # Окно добавления чека
        L10nFormat("refund-add-bill"),
        MessageInput(add_bill, content_types=(ContentType.DOCUMENT,)),
        state=CreateRefundApply.ADD_BILL,
    ),
)
