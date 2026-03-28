from io import BytesIO
from typing import Any

from aiogram import F
from aiogram.exceptions import TelegramNetworkError
from aiogram.types import CallbackQuery, BufferedInputFile, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Url, Button, Next, Back, SwitchTo
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization

from env import TelegramKeys
from includes import get_available_templates, load_schema, validate_data, generate_document
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines.templates import CreateByTemplate

from aiogram_dialog import Dialog, Window, DialogManager, StartMode
from aiogram_dialog.widgets.text import Format, Const
from aiogram_dialog.widgets.kbd import Row, Button, SwitchTo
from aiogram_dialog.widgets.input import TextInput
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from state_machines.refund import CreateByRefund
from utils import L10nFormat, escape_mdv2
import os

# --- Хелперы ---
def get_refund_data(dialog_manager: DialogManager):
	return dialog_manager.dialog_data.get("refund", {})

def is_complete(data: dict):
	return all(data.get(k) for k in ("event", "reason", "amount", "requisites", "receipt_photo"))

def refund_summary(data: dict, l10n):
	return l10n(
		"refund_summary",
		event=data.get("event", "-"),
		reason=data.get("reason", "-"),
		amount=data.get("amount", "-"),
		requisites=data.get("requisites", "-"),
		receipt_photo=("+" if data.get("receipt_photo") else "-")
	)


# --- Callback handlers ---
from aiogram.types import CallbackQuery

async def on_send_clicked(c: CallbackQuery, widget, manager: DialogManager):
	data = get_refund_data(manager)
	if c.message:
		await c.message.answer(str(data))
	else:
		await c.answer(str(data))
	await manager.done()

async def on_cancel_clicked(c: CallbackQuery, widget, manager: DialogManager):
	await manager.done()

def make_edit_field_handler(field: str):
	async def handler(c: CallbackQuery, widget, manager: DialogManager):
		manager.dialog_data["edit_field"] = field
		await manager.switch_to(CreateByRefund.EDIT)
	return handler

async def on_save_field(c: Message, widget, manager: DialogManager, value: str):
	field = manager.dialog_data.get("edit_field")
	if field:
		manager.dialog_data.setdefault("refund", {})[field] = value
	await manager.switch_to(CreateByRefund.VIEW)

# --- Окно просмотра ---
async def view_getter(dialog_manager: DialogManager, **kwargs):
	l10n = dialog_manager.middleware_data.get("l10n", lambda k, **a: k)
	data = get_refund_data(dialog_manager)
	return {
		"summary": refund_summary(data, l10n),
		"edit_event": l10n("refund_edit_event"),
		"edit_reason": l10n("refund_edit_reason"),
		"edit_amount": l10n("refund_edit_amount"),
		"edit_requisites": l10n("refund_edit_requisites"),
		"edit_receipt": l10n("refund_edit_receipt"),
		"send": l10n("refund_send"),
		"cancel": l10n("refund_cancel"),
		"is_complete": is_complete(data),
	}

def get_view_window():
	return Window(
		Format("{summary}"),
		Row(
			Button(Const("{edit_event}"), id="edit_event", on_click=make_edit_field_handler("event")),
			Button(Const("{edit_reason}"), id="edit_reason", on_click=make_edit_field_handler("reason")),
			Button(Const("{edit_amount}"), id="edit_amount", on_click=make_edit_field_handler("amount")),
			Button(Const("{edit_requisites}"), id="edit_requisites", on_click=make_edit_field_handler("requisites")),
			Button(Const("{edit_receipt}"), id="edit_receipt", on_click=make_edit_field_handler("receipt_photo")),
		),
		Row(
			Button(Const("{send}"), id="send", on_click=on_send_clicked, when="is_complete"),
			Button(Const("{cancel}"), id="cancel", on_click=on_cancel_clicked),
		),
		state=CreateByRefund.VIEW,
		getter=view_getter,
	)

# --- Окно редактирования ---
async def edit_getter(dialog_manager: DialogManager, **kwargs):
	l10n = dialog_manager.middleware_data.get("l10n", lambda k, **a: k)
	field = dialog_manager.dialog_data.get("edit_field", "field")
	return {
		"edit_prompt": l10n(f"refund_edit_{field}") or "Введите значение:",
		"back": l10n("refund_back"),
	}

def get_edit_window():
	return Window(
		Format("{edit_prompt}"),
		TextInput(id="edit_input", on_success=on_save_field),
		Row(Button(Const("{back}"), id="back", on_click=lambda c, w, m: m.switch_to(CreateByRefund.VIEW))),
		state=CreateByRefund.EDIT,
		getter=edit_getter,
	)

# --- Dialog ---
refund_dialog = Dialog(
	get_view_window(),
	get_edit_window(),
)