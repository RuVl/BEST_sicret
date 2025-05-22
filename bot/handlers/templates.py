import tempfile

from aiogram import Router, F
from aiogram.filters import Command, or_f
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from fluent.runtime import FluentLocalization

from includes.jsonschema import load_schema, validate_data, generate_document
from keyboards.callback_factories import PaginatorFactory, TemplateFactory, AskDataFactory, ActionDataFactory
from keyboards.templates import choose_template_ikb
from state_machines.templates import CreateByTemplate, TemplateContext

router = Router()


@router.message(Command('create_document'))
async def choose_template(msg: Message, state: FSMContext, l10n: FluentLocalization):
	""" Ask for a template for creation """

	await state.clear()  # Clear previous states and data

	kb = choose_template_ikb()
	await msg.answer(l10n.format_value('choose-template'), reply_markup=kb)
	await state.set_state(CreateByTemplate.CHOOSE_TEMPLATE)


@router.callback_query(
	CreateByTemplate.CHOOSE_TEMPLATE,
	PaginatorFactory.page_changed()
)
async def change_page_when_choose_template(clb: CallbackQuery, callback_data: PaginatorFactory):
	""" Change page by PaginatorFactory when choose template """

	await clb.answer()
	kb = choose_template_ikb(page=callback_data.page)
	await clb.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(
	CreateByTemplate.CHOOSE_TEMPLATE,
	TemplateFactory.filter()
)
async def choose_template(clb: CallbackQuery, callback_data: TemplateFactory, l10n: FluentLocalization, state: FSMContext):
	""" The template was chosen. Ask for data for template from schema. """

	try:
		schema = load_schema(callback_data.name)
	except FileNotFoundError:
		await clb.answer(l10n.format_value('schema-not-found'), show_alert=True)
		return

	await clb.answer()

	tc = TemplateContext(schema)
	await state.update_data(template_name=callback_data.name, template_context=tc.to_json())

	await clb.message.edit_text(text=tc.render_view(l10n), reply_markup=tc.render_keyboard(l10n))
	await state.set_state(CreateByTemplate.VIEW)


@router.callback_query(
	CreateByTemplate.VIEW,
	PaginatorFactory.page_changed()
)
async def change_page_when_choose_property(clb: CallbackQuery, callback_data: PaginatorFactory, state: FSMContext, l10n: FluentLocalization):
	""" Change page by PaginatorFactory when choose property of the template """

	await clb.answer()
	state_data = await state.get_data()
	tc = TemplateContext.from_json(state_data.get('template_context'))
	ctx = tc.get_active()
	await clb.message.edit_reply_markup(reply_markup=ctx.render_keyboard(l10n, page=callback_data.page))


@router.callback_query(
	CreateByTemplate.VIEW,
	ActionDataFactory.filter(F.action == 'generate-document')
)
async def send_document(clb: CallbackQuery, state: FSMContext):
	""" Validate jsonschema and generate document """

	state_data = await state.get_data()
	template_name = state_data.get('template_name')
	tc = TemplateContext.from_json(state_data.get('template_context'))

	context = tc.render_context()
	schema = load_schema(template_name)
	success, error_msg = validate_data(schema, context)
	if not success:
		await clb.answer(error_msg, show_alert=True)
		return

	doc = generate_document(template_name, context)
	await clb.answer()  # Answer after successful doc generation

	# Save doc to the temporary file and send it
	with tempfile.NamedTemporaryFile('wb+', prefix='result', suffix='.docx') as fp:
		doc.save(fp)
		fp.seek(0)
		file = BufferedInputFile(fp.read(), filename=f'{template_name}.docx')
		await clb.message.answer_document(file)


@router.callback_query(
	CreateByTemplate.VIEW,
	AskDataFactory.filter()
)
async def select_property(clb: CallbackQuery, callback_data: AskDataFactory, state: FSMContext, l10n: FluentLocalization):
	"""
	Ask for data for template by clicking on the button.
	If parent_type=ctx (=current TemplateContext) type is array - move to child or create a new one.
	Otherwise, move to object property child.
	"""

	# Get schema with properties from state data
	state_data = await state.get_data()
	tc = TemplateContext.from_json(state_data.get('template_context'))

	# Create or get child
	ctx = tc.forward(callback_data.key)
	state_data.update(template_context=tc.to_json())  # bcs tc.forward mutate tc object

	await state.set_data(state_data)  # Remember to update state data
	await clb.answer()

	if ctx.is_primitive():  # Если примитивный тип - задаем вопрос пользователю и ждем ответа
		await clb.message.edit_text(text=ctx.ask_question(), reply_markup=ctx.render_keyboard(l10n))
		await state.set_state(CreateByTemplate.ADD)
	elif ctx.is_submenu():  # Если подменю - перемещаемся в него
		await clb.message.edit_text(text=ctx.render_view(l10n), reply_markup=ctx.render_keyboard(l10n))


@router.message(CreateByTemplate.ADD)
async def add_primitive_property(msg: Message, state: FSMContext, l10n: FluentLocalization):
	""" Add user data to template """

	state_data = await state.get_data()
	tc = TemplateContext.from_json(state_data.get('template_context'))
	ctx = tc.get_active()

	# Validate and set value
	try:
		ctx.set_value(msg.text, l10n)
	except ValueError as e:
		await msg.reply(str(e), reply_markup=ctx.render_keyboard(l10n))
		return

	ctx = tc.backward()  # Return to previous view
	state_data.update(template_context=tc.to_json())  # Update state data
	await state.set_data(state_data)

	await msg.answer(text=ctx.render_view(l10n), reply_markup=ctx.render_keyboard(l10n))
	await state.set_state(CreateByTemplate.VIEW)


@router.callback_query(
	or_f(CreateByTemplate.ADD, CreateByTemplate.VIEW),
	ActionDataFactory.filter(F.action.in_({'back', 'delete'}))
)
async def cancel_adding_property(clb: CallbackQuery, callback_data: ActionDataFactory, state: FSMContext, l10n: FluentLocalization):
	""" Cancel adding property or exit from submenu """

	state_data = await state.get_data()
	tc = TemplateContext.from_json(state_data.get('template_context'))

	ctx = tc.backward() or tc if callback_data.action == 'back' else tc.delete_child()
	state_data.update(template_context=tc.to_json())

	await state.set_data(state_data)
	await clb.answer()

	await clb.message.edit_text(text=ctx.render_view(l10n), reply_markup=ctx.render_keyboard(l10n))
	await state.set_state(CreateByTemplate.VIEW)
