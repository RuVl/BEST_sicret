"""
Упрощенная версия диалога request_refund на основе универсальной системы шаблонов.
"""
from typing import Any

from aiogram.types import CallbackQuery
from aiogram_dialog import DialogManager
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession

from database.methods.payment import create_payment
from database.methods.person import get_person_by_telegram_id
from database.methods.refund import create_refund
from dialogs.user.form_by_schema import create_form_dialog, start_form_dialog
from env import TelegramKeys
from middlewares import L10N_FORMAT_KEY, SESSION_KEY
from state_machines.form_by_schema import FormBySchema
from utils import escape_mdv2

# Создаем диалог на основе универсального
request_refund_dialog = create_form_dialog(
    schema_name="request_refund",
    form_title="Заявка на возврат средств",
    form_description="Рефанд - это возможность вернуть потраченные на нужды Best'a личные средства.",
    initial_state=FormBySchema.VIEW
)


async def save_refund_callback(
    clb: CallbackQuery,
    dialog_manager: DialogManager,
    data: dict[str, Any]
):
    """Callback для сохранения данных рефанда в БД"""
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    
    name = data.get('name')
    event = data.get('event')
    reason = data.get('reason')
    amount = data.get('amount')
    card_number = data.get('card_number')
    
    # Получаем person_id
    person = await get_person_by_telegram_id(session, clb.from_user.id)
    if not person:
        await clb.answer("Ошибка: пользователь не найден", show_alert=True)
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
    
    await clb.answer("Заявка принята, Казначей свяжется с Вами в ближайшее время", show_alert=True)
    await dialog_manager.done()


async def start_request_refund(dialog_manager: DialogManager):
    """Запуск диалога запроса рефанда"""
    await start_form_dialog(
        dialog_manager=dialog_manager,
        schema_name="request_refund",
        form_title="Заявка на возврат средств",
        form_description="Рефанд - это возможность вернуть потраченные на нужды Best'a личные средства.",
        save_callback=save_refund_callback,
        initial_state=FormBySchema.VIEW
    )

