from pathlib import Path
from typing import Any

from aiogram import F
from aiogram.enums import ButtonStyle, ChatAction, ContentType
from aiogram.types import CallbackQuery, FSInputFile, Message
from aiogram.utils.chat_action import ChatActionSender
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, MessageInput, TextInput
from aiogram_dialog.widgets.kbd import Button, ScrollingGroup, Select, SwitchTo
from aiogram_dialog.widgets.style import Style
from aiogram_dialog.widgets.text import Format, Multi
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from env import settings
from includes import load_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY, LOGGING_KEY
from state_machines import CreateRefundApply
from utils import escape_mdv2, L10nFormat

DIALOG_SCHEMA = "refunds/apply.json"


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
            schema = load_schema(DIALOG_SCHEMA)
            ctx = create_context(schema)
            dialog_manager.dialog_data.update(ctx=ctx)
        except FileNotFoundError as e:
            await log.aexception("Failed to load refunds jsonschema", exc_info=e)
            return {
                "view": l10n.format_value("refund-schema-not-found"),
                "data_kb": [],
                "action_kb": [],
                "bill_filename": "",
                "can_send": False,
            }

    bill_filename = dialog_manager.dialog_data.get("bill_filename")
    return {
        "view": ctx.render_view(l10n),
        "data_kb": ctx.render_data_kb(l10n),
        "action_kb": ctx.render_action_kb(l10n),
        "bill_filename": escape_mdv2(bill_filename) or "",
        "can_send": bill_filename and ctx.can_generate(),
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


async def send_apply(
    clb: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    logger: FilteringBoundLogger = dialog_manager.middleware_data.get(LOGGING_KEY)
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    ctx: BaseContext = dialog_manager.dialog_data.get("ctx")

    raw_data = ctx.generate_context()
    schema = load_schema(DIALOG_SCHEMA)

    success, error_msg = validate_data(schema, raw_data)
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return

    raw_data["bill_filename"] = dialog_manager.dialog_data.get("bill_filename")
    raw_data["username"] = clb.from_user.username or clb.from_user.id

    bill_path = dialog_manager.dialog_data.get("bill_path")
    file = FSInputFile(bill_path, raw_data["bill_filename"])

    recipient_id = settings.telegram.TREASURER_ID or clb.from_user.id
    data = {k: escape_mdv2(v) for k, v in raw_data.items()}

    await logger.ainfo(
        "Sending refund apply",
        recipient_id=recipient_id,
        bill_path=bill_path,
        raw_data=raw_data,
    )
    await clb.bot.send_document(
        recipient_id,
        document=file,
        caption=l10n.format_value("treasure-refund-apply", args=data),
    )

    await clb.answer(l10n.format_value("refund-apply-was-sent"))
    await dialog_manager.done()


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
async def download_bill(
    msg: Message,
    widget: MessageInput,
    dialog_manager: DialogManager,
) -> None:
    logger: FilteringBoundLogger = dialog_manager.middleware_data.get(LOGGING_KEY)

    document = msg.document
    if document.file_size > 5 * 1024 * 1024:  # 5 MB
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await msg.reply(l10n.format_value("refund-bill-too-big"))
        return

    # мб это вынести в инициализацию проекта
    settings.project.REFUND_BILLS_DIR.mkdir(parents=True, exist_ok=True)

    # Удаляем предыдущий загруженный чек
    if old_bill_path := dialog_manager.dialog_data.get("bill_path"):
        await logger.ainfo("Delete old refund", file_path=old_bill_path)
        Path(old_bill_path).unlink(missing_ok=True)

    # Формируем путь для нового чека
    filename = Path(document.file_name or "no_name")
    save_filename = f"{filename.stem}_{document.file_id}{filename.suffix}"
    file_path = settings.project.REFUND_BILLS_DIR / save_filename

    async with ChatActionSender(
        bot=msg.bot,
        chat_id=msg.chat.id,
        action=ChatAction.UPLOAD_DOCUMENT,
        initial_sleep=0,
    ):
        await logger.ainfo("Downloading refund bill", file_path=file_path)
        file = await msg.bot.get_file(document.file_id)
        await msg.bot.download_file(file.file_path, destination=file_path)

    # мб проверку на тип файла добавить (pdf, jpg, etc.)
    dialog_manager.dialog_data["bill_filename"] = str(filename)
    dialog_manager.dialog_data["bill_path"] = file_path

    await dialog_manager.switch_to(CreateRefundApply.VIEW)


refund_dialog = Dialog(
    Window(
        Multi(
            Format("{view}"),
            L10nFormat("refund-bill-view"),
        ),
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
        SwitchTo(
            L10nFormat("refund-add-bill-btn"),
            id="add_bill",
            state=CreateRefundApply.ADD_BILL,
        ),
        Button(
            L10nFormat("refund-send-btn"),
            id="send_treasure",
            on_click=send_apply,
            when=F["can_send"],
            style=Style(style=ButtonStyle.SUCCESS, emoji_id="5388971216629412467"),
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
        MessageInput(download_bill, content_types=ContentType.DOCUMENT),
        SwitchTo(L10nFormat("back"), id="back", state=CreateRefundApply.VIEW),
        state=CreateRefundApply.ADD_BILL,
    ),
)
