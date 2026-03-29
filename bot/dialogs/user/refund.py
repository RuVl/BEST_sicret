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
	return all(data.get(k) for k in ("reason", "amount", "requisites", "receipt-photo"))

def refund_summary(data: dict, l10n):
	return l10n(
		"refund_summary",
		reason=escape_mdv2(data.get("reason", "-")),
		amount=escape_mdv2(data.get("amount", "-")),
		requisites=escape_mdv2(data.get("requisites", "-")),
		receipt_photo="+" if data.get("receipt-photo") else "-"
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
		from includes import load_schema
		from includes.templates.contexts.primitive_context import PrimitiveContext
		schema = load_schema("refund")
		field_schema = schema["properties"].get(field)
		if not field_schema:
			await c.answer("Ошибка: поле не найдено в схеме", show_alert=True)
			return
		l10n = manager.middleware_data.get("l10n", lambda k, **a: k)
		try:
			ctx = PrimitiveContext(field_schema)
			parsed_value = ctx.parse(value)
			manager.dialog_data.setdefault("refund", {})[field] = parsed_value
		except Exception as e:
			err_key = str(e)
			if err_key in ("invalid-integer-input", "invalid-number-input", "invalid-boolean-input", "invalid-type"):
				msg = l10n(err_key)
			elif err_key == "invalid-pattern":
				msg = l10n("invalid-type")
			elif err_key == "invalid-value":
				msg = l10n("invalid-type")
			else:
				msg = f"Ошибка: {err_key}"
			await c.answer(msg, show_alert=True)
			return
	await manager.switch_to(CreateByRefund.VIEW)

# --- Окно просмотра ---
async def view_getter(dialog_manager: DialogManager, **kwargs):
	l10n = dialog_manager.middleware_data.get("l10n", lambda k, **a: k)
	data = get_refund_data(dialog_manager)
	def _l10n(key, **kwargs):
		if hasattr(l10n, "format_value"):
			return l10n.format_value(key, args=kwargs)
		return l10n(key, **kwargs)
	return {
		"summary": refund_summary(data, _l10n),
		"edit_reason": _l10n("refund_edit_reason"),
		"edit_amount": _l10n("refund_edit_amount"),
		"edit_requisites": _l10n("refund_edit_requisites"),
		"edit_receipt": _l10n("refund_edit_receipt"),
		"send": _l10n("refund_send"),
		"cancel": _l10n("refund_cancel"),
		"is_complete": is_complete(data),
	}

def get_view_window():
	return Window(
		Format("{summary}"),
		Row(
			Button(Format("{edit_reason}"), id="edit_reason", on_click=make_edit_field_handler("reason")),
			Button(Format("{edit_amount}"), id="edit_amount", on_click=make_edit_field_handler("amount")),
			Button(Format("{edit_requisites}"), id="edit_requisites", on_click=make_edit_field_handler("requisites")),
			Button(Format("{edit_receipt}"), id="edit_receipt", on_click=make_edit_field_handler("receipt-photo")),
		),
		Row(
			Button(Format("{send}"), id="send", on_click=on_send_clicked, when="is_complete"),
			Button(Format("{cancel}"), id="cancel", on_click=on_cancel_clicked),
		),
		state=CreateByRefund.VIEW,
		getter=view_getter,
		parse_mode="MarkdownV2",
	)

# --- Окно редактирования ---
async def edit_getter(dialog_manager: DialogManager, **kwargs):
	l10n = dialog_manager.middleware_data.get("l10n", lambda k, **a: k)
	field = dialog_manager.dialog_data.get("edit_field", "field")
	def _l10n(key, **kwargs):
		if hasattr(l10n, "format_value"):
			return l10n.format_value(key, args=kwargs)
		return l10n(key, **kwargs)
	from utils import escape_mdv2
	return {
		"edit_prompt": _l10n(f"refund_edit_{escape_mdv2(field)}"),
		"back": _l10n("refund_back"),
	}

def get_edit_window():
	return Window(
			Format("{edit_prompt}"),
			TextInput(id="edit_input", on_success=on_save_field),
			Row(Button(Format("{back}"), id="back", on_click=lambda c, w, m: m.switch_to(CreateByRefund.VIEW))),
			state=CreateByRefund.EDIT,
			getter=edit_getter,
			parse_mode="MarkdownV2",
	)

# --- Dialog ---
refund_dialog = Dialog(
	get_view_window(),
	get_edit_window(),
)