from aiogram import F
from aiogram.types import CallbackQuery, Message, PhotoSize
from aiogram_dialog import Dialog, Window, DialogManager

from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Button, Back, SwitchTo
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization
from includes import load_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines.refund import CreateByRefund

from aiogram_dialog.widgets.input import MessageInput
from utils import escape_mdv2

from sqlalchemy import select
from database.main import async_session
from database.models.refund import Refund
from database.models.person import Person
from database.models.payment import Payment



# --- Инициализация refund context ---
def get_refund_context(dialog_manager: DialogManager) -> BaseContext:
    ctx = dialog_manager.dialog_data.get("context")
    if ctx is None:
        schema = load_schema("refund")
        ctx = create_context(schema)
        dialog_manager.dialog_data["context"] = ctx
    return ctx

# ========== Окно просмотра ========== 


async def get_refund_view(dialog_manager: DialogManager, **_kwargs):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context = get_refund_context(dialog_manager)
    data = {
        'view': context.render_view(l10n),
        'data_kb': context.render_data_kb(l10n),
        'can_send': context.filled_required(),
        'refund_send_button': l10n.format_value('refund_send_button'),
    }
    return data

async def on_refund_data_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, field: str):
    dialog_manager.dialog_data['edit_field'] = field
    await dialog_manager.switch_to(CreateByRefund.EDIT)

async def on_refund_send(clb: CallbackQuery, _select: Button, dialog_manager: DialogManager):
    context = get_refund_context(dialog_manager)
    data = context.generate_context() if context else {}
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    schema = load_schema("refund")
    success, error_msg = validate_data(schema, data)
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return

    # --- Сохранение заявки в БД ---
    async with async_session() as session:
        tg_id = clb.from_user.id
        person = await session.scalar(select(Person).where(Person.telegram_id == tg_id))
        if not person:
            person = Person(telegram_id=tg_id, full_name=clb.from_user.full_name or "")
            session.add(person)
            await session.flush()

        # Получить payment_id из данных 
        payment_id = data.get('payment_id')
        if not payment_id:
            payment = await session.scalar(select(Payment).where(Payment.id == person.payment_id))
            if not payment:
                msg = l10n.format_value('refund_no_payment_error') if l10n else '0'
                await clb.answer(msg, show_alert=True)
                return
            payment_id = payment.id

        refund = Refund(
            name=data.get('reason', ''),
            description=data.get('requisites', ''),
            customer_id=person.id,
            payment_id=payment_id,
        )
        session.add(refund)
        await session.commit()

    await dialog_manager.done()

# ========== Окно редактирования ========== 
async def get_refund_edit(dialog_manager: DialogManager, **_kwargs):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context = get_refund_context(dialog_manager)
    field = dialog_manager.dialog_data.get('edit_field')
    field_ctx = context.get_property(field) if context else None
    data = {
        'question': field_ctx.ask_question() if field_ctx else '',
        'can_back': True,
        'refund_back_button': l10n.format_value('refund_back_button'),
    }
    return data

async def set_refund_property(msg: Message, _: object, dialog_manager: DialogManager):
    context = get_refund_context(dialog_manager)
    field = dialog_manager.dialog_data.get('edit_field')
    field_ctx = context.get_property(field) if context else None
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    try:
        if not isinstance(field_ctx, PrimitiveContext):
            raise ValueError(l10n.format_value('refund_invalid_field'))
        if hasattr(msg, 'photo') and msg.photo:
            photo: PhotoSize = msg.photo[-1]
            field_ctx.set_value(photo.file_id)
        elif msg.text is not None:
            parsed_value = field_ctx.parse(msg.text)
            field_ctx.set_value(parsed_value)
        else:
            raise ValueError(l10n.format_value('refund_invalid_field'))
    except Exception as e:
        msg_text = l10n.format_value('refund_error', {'error': str(e)})
        await msg.answer(msg_text)
        return
    await dialog_manager.switch_to(CreateByRefund.VIEW)


# ========== Диалог========== 
refund_dialog = Dialog(
    Window(
        Multi(
            Format('{view}\n'),
            sep=''
        ),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='refund_field',
                item_id_getter=lambda x: x[1],
                items='data_kb',
                on_click=on_refund_data_selected
            ),
            id='refund_scroll',
            width=2,
            height=5,
            hide_on_single_page=True
        ),
        Row(
            Button(Format('{refund_send_button}'), id='refund_send', on_click=on_refund_send, when=F['can_send'])
        ),
        getter=get_refund_view,
        state=CreateByRefund.VIEW
    ),
    Window(
        Format('{question}'),
        MessageInput(set_refund_property),
        Row(Button(Format('{refund_back_button}'), id='refund_back', on_click=lambda c, w, m: m.switch_to(CreateByRefund.VIEW))),
        getter=get_refund_edit,
        state=CreateByRefund.EDIT,
    )
)