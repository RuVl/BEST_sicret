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
from utils import L10nFormat, escape_mdv2


# ========== Окно выбора шаблона ==========
async def get_template_list(**_kwargs) -> dict[str, Any]:
	return {'templates': get_available_templates()}


async def on_template_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, template_name: str):
	""" Try to load schema. If success - save in fsm and continue, else show alert """
	l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

	try:
		schema = load_schema(template_name)
		context = create_context(schema)
	except FileNotFoundError:
		await clb.answer(l10n.format_value('schema-not-found'), show_alert=True)
		return

	# Send notification to president if exists
	if TelegramKeys.PRESIDENT_ID:
		await clb.bot.send_message(
			TelegramKeys.PRESIDENT_ID,
			l10n.format_value('template-chosen', args={
				'template_name': escape_mdv2(template_name),
				'by_username': escape_mdv2(clb.from_user.username)
			})
		)

	dialog_manager.dialog_data.update(template_name=template_name, context=context)
	await dialog_manager.switch_to(CreateByTemplate.ADD if isinstance(context, PrimitiveContext) else CreateByTemplate.VIEW)


# ========== Окно просмотра ==========
async def get_template_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
	l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
	context: BaseContext = dialog_manager.dialog_data.get('context')
	return {
		'view': context.render_view(l10n),
		'data_kb': context.render_data_kb(l10n),
		'action_kb': context.render_action_kb(l10n),
		'can_generate': context.can_generate(),
	}


async def on_data_selected(_clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, data: str):
	context: BaseContext = dialog_manager.dialog_data.get('context')
	context = context.view(data)

	dialog_manager.dialog_data.update(context=context)
	await dialog_manager.switch_to(CreateByTemplate.ADD if isinstance(context, PrimitiveContext) else CreateByTemplate.VIEW)


async def on_action_selected(_clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, action: str):
	context: BaseContext = dialog_manager.dialog_data.get('context')
	context = context.do(action)

	dialog_manager.dialog_data.update(context=context)
	await dialog_manager.switch_to(CreateByTemplate.VIEW)


async def response_document(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager):
	l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
	template_name: str = dialog_manager.dialog_data.get('template_name')
	context: BaseContext = dialog_manager.dialog_data.get('context')

	data = context.generate_context()
	schema = load_schema(template_name)
	success, error_msg = validate_data(schema, data)
	if not success:
		await clb.answer(error_msg, show_alert=True)
		return

	doc = generate_document(template_name, data)
	buffer = BytesIO()
	doc.save(buffer)
	file = BufferedInputFile(buffer.getvalue(), filename=f'{template_name}.docx')

	try:
		sent_doc = await clb.message.answer_document(file)

		# Send it to president if exist
		if TelegramKeys.PRESIDENT_ID:
			await clb.bot.send_message(
				TelegramKeys.PRESIDENT_ID,
				l10n.format_value('document-generated', args={
					'template_name': escape_mdv2(template_name),
					'by_username': escape_mdv2(clb.from_user.username)
				})
			)
			await sent_doc.forward(TelegramKeys.PRESIDENT_ID)

	except TelegramNetworkError as e:
		await clb.answer(l10n.format_value('telegram-network-error'), show_alert=True)
		raise e


# ========== Окно редактирования ==========
async def get_property_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
	l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
	context: PrimitiveContext = dialog_manager.dialog_data.get('context')
	return {
		'question': context.ask_question(),
		'action_kb': context.render_action_kb(l10n),
		'can_generate': context.can_generate(),
	}


async def set_property(msg: Message, _: TextInput, dialog_manager: DialogManager, value: str):
	context: PrimitiveContext = dialog_manager.dialog_data.get('context')
	try:
		parsed_value = context.parse(value)
	except ValueError as e:
		l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
		await msg.answer(l10n.format_value(str(e)))
		return

	context.set_value(parsed_value)
	try:  # try to go back
		context = context.do('back')
	except ValueError:
		await dialog_manager.switch_to(CreateByTemplate.VIEW)
		return

	dialog_manager.dialog_data.update(context=context)
	await dialog_manager.switch_to(CreateByTemplate.VIEW)


template_dialog = Dialog(
	Window(  # Окно с выбором шаблона
		L10nFormat('choose-template'),
		ScrollingGroup(
			Select(
				Format('{item}'),
				id='templates_select',
				item_id_getter=lambda x: x,
				items='templates',
				on_click=on_template_selected
			),
			id='templates_scroll',
			width=2,
			height=5,
			hide_on_single_page=True
		),
		Row(Url(L10nFormat('templates-link-text'), url=L10nFormat('templates-link'))),
		getter=get_template_list,
		state=CreateByTemplate.CHOOSE_TEMPLATE,
		preview_add_transitions=[
			SwitchTo('', '', CreateByTemplate.VIEW),
			SwitchTo('', '', CreateByTemplate.ADD),
		]
	),
	Window(  # Окно просмотра
		Multi(
			Format('{view}\n\n'),
			# Below code make: * - Обязательное поле (_italic_) 
			Const(r'_\* \- '),
			L10nFormat('required-hint'),
			Const('_'),
			sep=''
		),
		ScrollingGroup(
			Select(
				Format('{item[0]}'),
				id='template_change',
				item_id_getter=lambda x: x[1],
				items='data_kb',
				on_click=on_data_selected
			),
			id='template_scroll',
			width=2,
			height=5,
			hide_on_single_page=True
		),
		Select(
			Format('{item[0]}'),
			id='template_action',
			item_id_getter=lambda x: x[1],
			items='action_kb',
			on_click=on_action_selected
		),
		Row(Button(
			L10nFormat('generate-document'),
			id='generate_document',
			on_click=response_document,
			when=F['can_generate']
		)),
		getter=get_template_context,
		state=CreateByTemplate.VIEW,
		preview_add_transitions=[
			SwitchTo('', '', CreateByTemplate.VIEW),
			Next()
		]
	),
	Window(  # Окно редактирования
		Format('{question}'),
		TextInput('input_property', on_success=set_property),
		Select(
			Format('{item[0]}'),
			id='template_action',
			item_id_getter=lambda x: x[1],
			items='action_kb',
			on_click=on_action_selected
		),
		getter=get_property_context,
		state=CreateByTemplate.ADD,
		preview_add_transitions=[Back()]
	)
)
