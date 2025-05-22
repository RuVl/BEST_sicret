from io import BytesIO
from typing import Any

from aiogram import F
from aiogram.types import CallbackQuery, BufferedInputFile
from aiogram_dialog import Dialog, Window, LaunchMode, DialogManager
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Url, Button
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization

from includes import get_available_templates, load_schema, validate_data, generate_document
from includes.templates import create_context
from includes.templates.contexts import BaseContext
from middlewares import L10N_FORMAT_KEY
from state_machines.templates import CreateByTemplate
from utils import L10nFormat


async def get_template_list(**_kwargs) -> dict:
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

	dialog_manager.dialog_data.update(template_name=template_name, context=context)
	await dialog_manager.switch_to(CreateByTemplate.VIEW)


async def get_template_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
	l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
	context: BaseContext = dialog_manager.dialog_data.get('context')
	return {
		'can_generate': context.can_generate(),
		'view': context.render_view(l10n),
		'data_kb': context.render_data_kb(l10n),
		'action_kb': context.render_action_kb(l10n),
	}


async def on_data_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, data: str):
	context: BaseContext = dialog_manager.dialog_data.get('context')
	context.view(data)


async def on_action_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, action: str):
	context: BaseContext = dialog_manager.dialog_data.get('context')
	context.do(action)


async def response_document(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, action: str):
	template_name: str = dialog_manager.dialog_data.get('template_name')
	context: BaseContext = dialog_manager.dialog_data.get('context')

	context.generate_context()
	schema = load_schema(template_name)
	success, error_msg = validate_data(schema, context)
	if not success:
		await clb.answer(error_msg, show_alert=True)
		return

	await clb.answer()  # Answer before doc generation
	doc = generate_document(template_name, context)

	buffer = BytesIO()
	doc.save(buffer)
	buffer.seek(0)  # обязательно вернуться в начало буфера перед отправкой
	await clb.message.answer_document(BufferedInputFile(buffer, filename=f'{template_name}.docx'))


template_dialog = Dialog(
	Window(
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
		Row(Url(L10nFormat('templates-link-text'), url=L10nFormat('templates-link-url'))),
		getter=get_template_list,
		state=CreateByTemplate.CHOOSE_TEMPLATE
	),
	Window(
		Format('{view}'),
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
			id='template_change',
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
	),
	Window(
		state=CreateByTemplate.ADD,
	),
	launch_mode=LaunchMode.STANDARD
)
