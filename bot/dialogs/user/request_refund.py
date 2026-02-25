from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Row, Button, Back
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession

from database.methods.payment import create_payment
from database.methods.person import get_person_by_telegram_id
from database.methods.refund import create_refund
from env import TelegramKeys
from middlewares import L10N_FORMAT_KEY, SESSION_KEY
from state_machines.request_refund import RequestRefund
from utils import escape_mdv2, L10nFormat


# ========== Главная форма ==========
async def get_main_form_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные главной формы """
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    name = dialog_manager.dialog_data.get('name', l10n.format_value('field-name'))
    event = dialog_manager.dialog_data.get('event', l10n.format_value('field-event'))
    reason = dialog_manager.dialog_data.get('reason', l10n.format_value('field-reason'))
    amount = dialog_manager.dialog_data.get('amount', l10n.format_value('field-amount'))
    card_number = dialog_manager.dialog_data.get('card_number', l10n.format_value('field-card-number'))
    
    # Экранируем пользовательский ввод для MarkdownV2
    return {
        'name': escape_mdv2(name) if isinstance(name, str) else name,
        'event': escape_mdv2(event) if isinstance(event, str) else event,
        'reason': escape_mdv2(reason) if isinstance(reason, str) else reason,
        'amount': escape_mdv2(amount) if isinstance(amount, str) else amount,
        'card_number': escape_mdv2(card_number) if isinstance(card_number, str) else card_number
    }


async def on_name_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу имени """
    await dialog_manager.switch_to(RequestRefund.INPUT_NAME)


async def on_event_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу мероприятия """
    await dialog_manager.switch_to(RequestRefund.INPUT_EVENT)


async def on_reason_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу причины """
    await dialog_manager.switch_to(RequestRefund.INPUT_REASON)


async def on_amount_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу суммы """
    await dialog_manager.switch_to(RequestRefund.INPUT_AMOUNT)


async def on_card_number_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу номера карты """
    await dialog_manager.switch_to(RequestRefund.INPUT_CARD_NUMBER)


async def on_review_form_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к просмотру формы для редактирования """
    await dialog_manager.switch_to(RequestRefund.REVIEW_FORM)


# ========== Ввод имени ==========
async def get_name_input_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_name_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенного имени """
    dialog_manager.dialog_data['name'] = value
    # возвращаемся к главной форме явным переходом, иначе
    # `done()` завершает весь диалог (stack очищается после switch_to)
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Ввод мероприятия ==========
async def get_event_input_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_event_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенного мероприятия """
    dialog_manager.dialog_data['event'] = value
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Ввод причины ==========
async def get_reason_input_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_reason_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенной причины """
    dialog_manager.dialog_data['reason'] = value
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Ввод суммы ==========
async def get_amount_input_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_amount_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенной суммы """
    try:
        # Проверяем, что это число
        amount = int(value)
        dialog_manager.dialog_data['amount'] = str(amount)
    except ValueError:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await msg.answer(l10n.format_value('enter-number'))
        return
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Ввод номера карты ==========
async def get_card_number_input_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_card_number_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенного номера карты """
    dialog_manager.dialog_data['card_number'] = value
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Просмотр формы для редактирования ==========
async def get_review_form_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные для просмотра формы """
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    name = dialog_manager.dialog_data.get('name', '')
    event = dialog_manager.dialog_data.get('event', '')
    reason = dialog_manager.dialog_data.get('reason', '')
    amount = dialog_manager.dialog_data.get('amount', '')
    card_number = dialog_manager.dialog_data.get('card_number', '')
    
    # Экранируем пользовательский ввод для MarkdownV2
    name_escaped = escape_mdv2(name) if name else ''
    event_escaped = escape_mdv2(event) if event else ''
    reason_escaped = escape_mdv2(reason) if reason else ''
    amount_escaped = escape_mdv2(amount) if amount else ''
    card_number_escaped = escape_mdv2(card_number) if card_number else ''
    
    return {
        'name': name_escaped,
        'event': event_escaped,
        'reason': reason_escaped,
        'amount': amount_escaped,
        'card_number': card_number_escaped
    }


async def on_confirm_review_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к итоговому просмотру заявки """
    # Проверяем, что все поля заполнены
    name = dialog_manager.dialog_data.get('name')
    event = dialog_manager.dialog_data.get('event')
    reason = dialog_manager.dialog_data.get('reason')
    amount = dialog_manager.dialog_data.get('amount')
    card_number = dialog_manager.dialog_data.get('card_number')
    
    if not name or not event or not reason or not amount or not card_number:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await _clb.answer(l10n.format_value('fill-all-fields'), show_alert=True)
        return
    
    await dialog_manager.switch_to(RequestRefund.REVIEW_APPLICATION)


# ========== Просмотр итоговой заявки ==========
async def get_review_application_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные для итогового просмотра заявки """
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    name = dialog_manager.dialog_data.get('name', '')
    event = dialog_manager.dialog_data.get('event', '')
    reason = dialog_manager.dialog_data.get('reason', '')
    amount = dialog_manager.dialog_data.get('amount', '')
    card_number = dialog_manager.dialog_data.get('card_number', '')
    
    # Экранируем пользовательский ввод для MarkdownV2
    return {
        'name': escape_mdv2(name) if name else '',
        'event': escape_mdv2(event) if event else '',
        'reason': escape_mdv2(reason) if reason else '',
        'amount': escape_mdv2(amount) if amount else '',
        'card_number': escape_mdv2(card_number) if card_number else ''
    }


async def on_confirm_application(clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Подтверждение и создание заявки на рефанд """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    
    name = dialog_manager.dialog_data.get('name')
    event = dialog_manager.dialog_data.get('event')
    reason = dialog_manager.dialog_data.get('reason')
    amount_str = dialog_manager.dialog_data.get('amount')
    card_number = dialog_manager.dialog_data.get('card_number')
    
    # Получаем person_id
    person = await get_person_by_telegram_id(session, clb.from_user.id)
    if not person:
        await clb.answer(l10n.format_value('user-not-found'), show_alert=True)
        return
    
    # Преобразуем сумму в число
    try:
        amount = int(amount_str)
    except (ValueError, TypeError):
        await clb.answer(l10n.format_value('invalid-amount'), show_alert=True)
        return
    
    # Создаем Payment
    payment = await create_payment(
        session=session,
        cost=amount,
        is_paid=False
    )
    
    # Формируем описание для Refund
    description = f"Мероприятие: {event}\nПричина: {reason}\nНомер карты: {card_number}"
    
    # Создаем Refund
    refund = await create_refund(
        session=session,
        name=name,
        customer_id=person.id,
        payment_id=payment.id,
        description=description
    )
    
    # Отправляем уведомление казначею
    if TelegramKeys.TREASURER_ID:
        await clb.bot.send_message(
            TelegramKeys.TREASURER_ID,
            f"Новая заявка на рефанд:\n"
            f"Имя: {escape_mdv2(name)}\n"
            f"Мероприятие: {escape_mdv2(event)}\n"
            f"Причина: {escape_mdv2(reason)}\n"
            f"Сумма: {amount} руб.\n"
            f"Номер карты: {escape_mdv2(card_number)}\n"
            f"ID заявки: {refund.id}"
        )
    
    await dialog_manager.switch_to(RequestRefund.CONFIRM_APPLICATION)


# ========== Подтверждение отправки ==========
async def get_confirm_data(**_kwargs) -> dict[str, Any]:
    return {}


request_refund_dialog = Dialog(
    Window(  # Главная форма
        Multi(
            L10nFormat('request-refund-description'),
            L10nFormat('request-refund-instruction'),
            Format("Имя: {name}\n"),
            Format("Мероприятие: {event}\n"),
            Format("Причина: {reason}\n"),
            Format("Сумма: {amount}\n"),
            Format("Номер карты: {card_number}"),
            sep="\n\n"
        ),
        Row(
            Button(
                L10nFormat('field-name'),
                id='input_name',
                on_click=on_name_clicked
            ),
            Button(
                L10nFormat('field-event'),
                id='input_event',
                on_click=on_event_clicked
            ),
            Button(
                L10nFormat('field-reason'),
                id='input_reason',
                on_click=on_reason_clicked
            )
        ),
        Row(
            Button(
                L10nFormat('field-amount'),
                id='input_amount',
                on_click=on_amount_clicked
            ),
            Button(
                L10nFormat('field-card-number'),
                id='input_card_number',
                on_click=on_card_number_clicked
            )
        ),
        Row(
            Button(
                L10nFormat('button-review-application'),
                id='review_form',
                on_click=on_review_form_clicked
            )
        ),
        getter=get_main_form_data,
        state=RequestRefund.MAIN_FORM,
    ),
    Window(  # Ввод имени
        L10nFormat('input-name'),
        TextInput('input_name', on_success=on_name_input),
        Back(L10nFormat('back')),
        getter=get_name_input_data,
        state=RequestRefund.INPUT_NAME,
    ),
    Window(  # Ввод мероприятия
        L10nFormat('input-event'),
        TextInput('input_event', on_success=on_event_input),
        Back(L10nFormat('back')),
        getter=get_event_input_data,
        state=RequestRefund.INPUT_EVENT,
    ),
    Window(  # Ввод причины
        L10nFormat('input-reason'),
        TextInput('input_reason', on_success=on_reason_input),
        Back(L10nFormat('back')),
        getter=get_reason_input_data,
        state=RequestRefund.INPUT_REASON,
    ),
    Window(  # Ввод суммы
        L10nFormat('input-amount'),
        TextInput('input_amount', on_success=on_amount_input),
        Back(L10nFormat('back')),
        getter=get_amount_input_data,
        state=RequestRefund.INPUT_AMOUNT,
    ),
    Window(  # Ввод номера карты
        L10nFormat('input-card-number'),
        TextInput('input_card_number', on_success=on_card_number_input),
        Back(L10nFormat('back')),
        getter=get_card_number_input_data,
        state=RequestRefund.INPUT_CARD_NUMBER,
    ),
    Window(  # Просмотр формы для редактирования
        Multi(
            L10nFormat('review-form-title'),
            Format("Имя: {name}\n"),
            Format("Мероприятие: {event}\n"),
            Format("Причина: {reason}\n"),
            Format("Сумма: {amount} руб.\n"),
            Format("Номер карты: {card_number}"),
            sep="\n\n"
        ),
        Row(
            Button(
                L10nFormat('button-confirm-submit-review'),
                id='confirm_review',
                on_click=on_confirm_review_clicked
            )
        ),
        Back(L10nFormat('back')),
        getter=get_review_form_data,
        state=RequestRefund.REVIEW_FORM,
    ),
    Window(  # Просмотр итоговой заявки
        Multi(
            L10nFormat('confirm-submit-header'),
            Format("Имя: {name}\n"),
            Format("Мероприятие: {event}\n"),
            Format("Причина: {reason}\n"),
            Format("Сумма: {amount} руб.\n"),
            Format("Номер карты: {card_number}"),
            sep="\n"
        ),
        Row(
            Button(
                L10nFormat('button-confirm-submit'),
                id='confirm_application',
                on_click=on_confirm_application
            )
        ),
        Back(L10nFormat('back')),
        getter=get_review_application_data,
        state=RequestRefund.REVIEW_APPLICATION,
    ),
    Window(  # Подтверждение отправки
        L10nFormat('application-accepted'),
        Button(
            L10nFormat('button-to-main-menu'),
            id='to_main_menu',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_confirm_data,
        state=RequestRefund.CONFIRM_APPLICATION,
    ),
)

