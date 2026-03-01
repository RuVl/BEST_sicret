from typing import Any

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import Row, Button, Back
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession

from database.methods.payment import get_payment_by_id
from database.methods.person import get_person_by_telegram_id
from database.methods.refund import create_refund, get_refund_by_id
from database.error_handler import handle_db_commit
from env import TelegramKeys
from middlewares import L10N_FORMAT_KEY, SESSION_KEY
from state_machines.request_refund import RequestRefund
from utils import L10nFormat, escape_mdv2


# ========== Главное меню ==========
async def get_main_form_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные главной формы """
    name = dialog_manager.dialog_data.get('name')
    event = dialog_manager.dialog_data.get('event')
    reason = dialog_manager.dialog_data.get('reason')
    amount = dialog_manager.dialog_data.get('amount')
    card_number = dialog_manager.dialog_data.get('card_number')
    
    return {
        'name': name if name else 'Не заполнено',
        'event': event if event else 'Не заполнено',
        'reason': reason if reason else 'Не заполнено',
        'amount': amount if amount else 'Не заполнено',
        'card_number': f"****{card_number[-4:]}" if card_number and len(card_number) >= 4 else 'Не заполнено'
    }


async def on_name_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу имени """
    await dialog_manager.switch_to(RequestRefund.INPUT_NAME)


async def on_event_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу события """
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
    """ Переход к форме просмотра/редактирования """
    await dialog_manager.switch_to(RequestRefund.REVIEW_FORM)


# ========== Ввод имени ==========
async def get_name_input_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    name = dialog_manager.dialog_data.get('name')
    return {'name': name if name else 'Не заполнено'}


async def on_name_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенного имени """
    dialog_manager.dialog_data['name'] = value
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Ввод события ==========
async def get_event_input_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    event = dialog_manager.dialog_data.get('event')
    return {'event': event if event else 'Не заполнено'}


async def on_event_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенного события """
    dialog_manager.dialog_data['event'] = value
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Ввод причины ==========
async def get_reason_input_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    reason = dialog_manager.dialog_data.get('reason')
    return {'reason': reason if reason else 'Не заполнено'}


async def on_reason_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенной причины """
    dialog_manager.dialog_data['reason'] = value
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Ввод суммы ==========
async def get_amount_input_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    amount = dialog_manager.dialog_data.get('amount')
    return {'amount': amount if amount else 'Не заполнено'}


async def on_amount_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенной суммы """
    try:
        amount = float(value)
        if amount <= 0:
            await msg.answer("Сумма должна быть положительным числом")
            return
        dialog_manager.dialog_data['amount'] = str(amount)
        await dialog_manager.switch_to(RequestRefund.MAIN_FORM)
    except ValueError:
        await msg.answer("Пожалуйста, введите корректную сумму (число с возможной десятичной точкой)")


# ========== Ввод номера карты ==========
async def get_card_number_input_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    card_number = dialog_manager.dialog_data.get('card_number')
    return {'card_number': card_number if card_number else 'Не заполнено'}


async def on_card_number_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенного номера карты """
    # Простая валидация номера карты (от 13 до 19 цифр)
    if not value.isdigit() or not (13 <= len(value) <= 19):
        await msg.answer("Пожалуйста, введите корректный номер карты (13-19 цифр)")
        return
    dialog_manager.dialog_data['card_number'] = value
    await dialog_manager.switch_to(RequestRefund.MAIN_FORM)


# ========== Форма просмотра ==========
async def get_review_form_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные для просмотра """
    name = dialog_manager.dialog_data.get('name', 'Не заполнено')
    event = dialog_manager.dialog_data.get('event', 'Не заполнено')
    reason = dialog_manager.dialog_data.get('reason', 'Не заполнено')
    
    return {
        'name': escape_mdv2(name) if name else 'Не заполнено',
        'event': escape_mdv2(event) if event else 'Не заполнено',
        'reason': escape_mdv2(reason) if reason else 'Не заполнено'
    }


async def on_confirm_review_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к подтверждению/редактированию заявки """
    # Проверяем, что нужные поля заполнены
    name = dialog_manager.dialog_data.get('name')
    event = dialog_manager.dialog_data.get('event')
    reason = dialog_manager.dialog_data.get('reason')
    amount = dialog_manager.dialog_data.get('amount')
    card_number = dialog_manager.dialog_data.get('card_number')
    
    if not all([name, event, reason, amount, card_number]):
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await _clb.answer(l10n.format_value('fill-all-fields'), show_alert=True)
        return
    
    await dialog_manager.switch_to(RequestRefund.REVIEW_APPLICATION)


# ========== Просмотр заявки ==========
async def get_review_application_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные заявки для просмотра перед отправкой """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    
    name = dialog_manager.dialog_data.get('name', '')
    event = dialog_manager.dialog_data.get('event', '')
    reason = dialog_manager.dialog_data.get('reason', '')
    amount = dialog_manager.dialog_data.get('amount', '0')
    card_number = dialog_manager.dialog_data.get('card_number', '****')
    payment_id = dialog_manager.dialog_data.get('payment_id')
    
    # Если есть payment_id, получаем информацию о платеже
    payment_info = ""
    if payment_id:
        payment = await get_payment_by_id(session, payment_id)
        if payment:
            payment_info = f"Платеж: {payment.payment_method if payment.payment_method else 'Unknown'}\n"
    
    return {
        'name': escape_mdv2(name) if name else '',
        'event': escape_mdv2(event) if event else '',
        'reason': escape_mdv2(reason) if reason else '',
        'amount': escape_mdv2(amount) if amount else '',
        'card_number': escape_mdv2(card_number[-4:]) if len(card_number) > 0 else '',  # Скрываем номер карты
        'payment_info': escape_mdv2(payment_info) if payment_info else ''
    }


async def on_confirm_application(clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Подтверждение и отправка заявки на рефанд """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    
    # Получаем все необходимые данные
    person = await get_person_by_telegram_id(session, clb.from_user.id)
    if not person:
        await clb.answer(l10n.format_value('user-not-found'), show_alert=True)
        return
    
    # Создаем заявку на рефанд
    refund_request = await create_refund(
        session=session,
        person_id=person.id,
        name=dialog_manager.dialog_data.get('name'),
        event=dialog_manager.dialog_data.get('event'),
        reason=dialog_manager.dialog_data.get('reason'),
        amount=float(dialog_manager.dialog_data.get('amount', 0)),
        card_number=dialog_manager.dialog_data.get('card_number'),
        payment_id=dialog_manager.dialog_data.get('payment_id')
    )
    
    # ✅ ОБРАБОТКА ОШИБОК БД: Централизованная обработка через error_handler
    success, error_msg = await handle_db_commit(session, l10n, "create refund request")
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return
    
    # Отправляем уведомление казначею
    if TelegramKeys.TREASURER_ID:
        await clb.bot.send_message(
            TelegramKeys.TREASURER_ID,
            f"Новая заявка на рефанд:\n"
            f"Имя: {dialog_manager.dialog_data.get('name')}\n"
            f"Событие: {dialog_manager.dialog_data.get('event')}\n"
            f"Сумма: {dialog_manager.dialog_data.get('amount')}\n"
            f"ID заявки: {refund_request.id}"
        )
    
    # Переходим на экран подтверждения
    await dialog_manager.switch_to(RequestRefund.CONFIRM_APPLICATION)


# ========== Подтверждение отправки ==========
async def get_confirm_application_data(**_kwargs) -> dict[str, Any]:
    return {}


request_refund_dialog = Dialog(
    Window(  # Главное меню заполнения рефанда
        Multi(
            L10nFormat('request-refund-main-menu'),
            Const('\n'),
            L10nFormat('request-refund-instruction'),
            Const('\n'),
            Format("Имя\\: {name}"),
            Format("Событие\\: {event}"),
            Format("Причина\\: {reason}"),
            Format("Сумма\\: {amount}"),
            Format("Карта\\: {card_number}"),
            sep="\n"
        ),
        Const('\n'),
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
            )
        ),
        Row(
            Button(
                L10nFormat('field-reason'),
                id='input_reason',
                on_click=on_reason_clicked
            ),
            Button(
                L10nFormat('field-amount'),
                id='input_amount',
                on_click=on_amount_clicked
            )
        ),
        Button(
            L10nFormat('field-card-number'),
            id='input_card_number',
            on_click=on_card_number_clicked
        ),
        Const('\n'),
        Button(
            L10nFormat('button-review-refund'),
            id='review_form',
            on_click=on_review_form_clicked,
            when=F['name'] & F['event'] & F['reason'] & F['amount'] & F['card_number']
        ),
        getter=get_main_form_data,
        state=RequestRefund.MAIN_FORM,
    ),
    Window(  # Ввод имени
        Multi(
            L10nFormat('input-name'),
            Format("Текущее значение\\: {name}"),
            sep="\n"
        ),
        TextInput('input_name', on_success=on_name_input),
        Button(
            L10nFormat('back'),
            id='back_from_name',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_name_input_data,
        state=RequestRefund.INPUT_NAME,
    ),
    Window(  # Ввод события
        Multi(
            L10nFormat('input-event'),
            Format("Текущее значение\\: {event}"),
            sep="\n"
        ),
        TextInput('input_event', on_success=on_event_input),
        Button(
            L10nFormat('back'),
            id='back_from_event',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_event_input_data,
        state=RequestRefund.INPUT_EVENT,
    ),
    Window(  # Ввод причины
        Multi(
            L10nFormat('input-reason'),
            Format("Текущее значение\\: {reason}"),
            sep="\n"
        ),
        TextInput('input_reason', on_success=on_reason_input),
        Button(
            L10nFormat('back'),
            id='back_from_reason',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_reason_input_data,
        state=RequestRefund.INPUT_REASON,
    ),
    Window(  # Ввод суммы
        Multi(
            L10nFormat('input-amount'),
            Format("Текущее значение\\: {amount}"),
            sep="\n"
        ),
        TextInput('input_amount', on_success=on_amount_input),
        Button(
            L10nFormat('back'),
            id='back_from_amount',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_amount_input_data,
        state=RequestRefund.INPUT_AMOUNT,
    ),
    Window(  # Ввод номера карты
        Multi(
            L10nFormat('input-card-number'),
            Format("Текущее значение\\: {card_number}"),
            sep="\n"
        ),
        TextInput('input_card_number', on_success=on_card_number_input),
        Button(
            L10nFormat('back'),
            id='back_from_card',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_card_number_input_data,
        state=RequestRefund.INPUT_CARD_NUMBER,
    ),
    Window(  # Форма просмотра
        Multi(
            L10nFormat('review-refund-header'),
            Format("Имя\\: {name}\n"),
            Format("Событие\\: {event}\n"),
            Format("Причина\\: {reason}\n"),
            sep=""
        ),
        Button(
            L10nFormat('button-confirm-refund'),
            id='confirm_review',
            on_click=on_confirm_review_clicked
        ),
        Button(
            L10nFormat('back'),
            id='back_from_review',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_review_form_data,
        state=RequestRefund.REVIEW_FORM,
    ),
    Window(  # Просмотр заявки перед отправкой
        Multi(
            L10nFormat('confirm-submit-header'),
            Format("Имя\\: {name}\n"),
            Format("Событие\\: {event}\n"),
            Format("Причина\\: {reason}\n"),
            Format("Сумма\\: {amount}\n"),
            Format("Карта\\: ****{card_number}\n"),
            sep=""
        ),
        Button(
            L10nFormat('button-submit-refund'),
            id='confirm_application',
            on_click=on_confirm_application
        ),
        Button(
            L10nFormat('back'),
            id='back_from_confirm',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.REVIEW_FORM)
        ),
        getter=get_review_application_data,
        state=RequestRefund.REVIEW_APPLICATION,
    ),
    Window(  # Подтверждение отправки
        L10nFormat('refund-application-accepted'),
        Button(
            L10nFormat('button-to-main-menu'),
            id='to_main_menu',
            on_click=lambda c, b, d: d.switch_to(RequestRefund.MAIN_FORM)
        ),
        getter=get_confirm_application_data,
        state=RequestRefund.CONFIRM_APPLICATION,
    ),
)
