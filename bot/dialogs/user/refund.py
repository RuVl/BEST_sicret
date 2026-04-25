from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from structlog import get_logger
from structlog.typing import FilteringBoundLogger

from includes import load_schema
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines import CreateRefundApply

logger: FilteringBoundLogger = get_logger("refund.create_apply")


# ========== Окно просмотра ==========
async def create_refund_apply(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    ctx: BaseContext = dialog_manager.dialog_data.get("ctx")

    if ctx is None:
        try:
            schema = load_schema("refunds/apply.json")
            ctx = create_context(schema)
            dialog_manager.dialog_data.update(ctx=ctx)
        except FileNotFoundError:
            await logger.aexception("Failed to load refunds/apply.json")
            return {
                "view": l10n.format_value("refund-schema-not-found"),
                "data_kb": [],
                "action_kb": [],
                "can_generate": False,
            }

    return {
        "view": ctx.render_view(l10n),
        "data_kb": ctx.render_data_kb(l10n),
        "action_kb": ctx.render_action_kb(l10n),
        "can_generate": ctx.can_generate(),
    }


async def on_data_selected(clb: CallbackQuery, select: Select, dialog_manager: DialogManager, data: str) -> None:
    ctx: BaseContext = dialog_manager.dialog_data.get("ctx")
    ctx = ctx.view(data)

    await clb.answer()
    dialog_manager.dialog_data.update(ctx=ctx)

    if isinstance(ctx, PrimitiveContext):
        await dialog_manager.switch_to(CreateRefundApply.EDIT)
    else:
        await dialog_manager.switch_to(CreateRefundApply.VIEW)


# ========== Окно редактирования ==========
async def get_property_context(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    ctx: BaseContext = dialog_manager.dialog_data.get("ctx")
    return {
        "question": ctx.ask_question(),
        "action_kb": ctx.render_action_kb(l10n),
        "can_generate": ctx.can_generate(),
    }


async def set_property(msg: Message, text_input: TextInput, dialog_manager: DialogManager, value: str) -> None:
    ctx: PrimitiveContext = dialog_manager.dialog_data.get("ctx")
    try:
        parsed_value = ctx.parse(value)
    except ValueError:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await msg.answer(l10n.format_value("invalid-value"))
        return

    logger.info(f"Setting {parsed_value} to context")
    ctx.set_value(parsed_value)
    ctx = ctx.do(ctx.BACK_ACTION)

    dialog_manager.dialog_data.update(ctx=ctx)
    await dialog_manager.switch_to(CreateRefundApply.VIEW)


async def on_action_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, action: str):
    ctx: PrimitiveContext = dialog_manager.dialog_data.get("ctx")
    ctx = ctx.do(action)

    dialog_manager.dialog_data.update(ctx=ctx)
    await dialog_manager.switch_to(CreateRefundApply.VIEW)


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
        getter=create_refund_apply,
        state=CreateRefundApply.VIEW,
    ),
    Window(  # Окно редактирования
        Format("{question}"),
        TextInput("input_property", on_success=set_property),  # type: ignore[arg-type]
        Select(
            Format("{item[0]}"),
            id="template_action",
            item_id_getter=lambda x: x[1],
            items="action_kb",
            on_click=on_action_selected
        ),
        getter=get_property_context,
        state=CreateRefundApply.EDIT,
    ),
)
