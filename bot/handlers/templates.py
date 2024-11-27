import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, FSInputFile
from fluent.runtime import FluentLocalization

from bot.includes.jsonschema import load_schema, validate_data, generate_document
from bot.keyboards.callback_factories import PaginatorFactory, TemplateFactory, AskActionFactory
from bot.keyboards.common.inline import cancel_ikb
from bot.keyboards.templates import choose_template_ikb, template_properties_ikb
from bot.state_machines.templates import CreateByTemplate
from bot.utils import escape_mdv2

router = Router()


@router.message(Command('create_document'))
async def choose_template(msg: Message, state: FSMContext, l10n: FluentLocalization):
    """ Ask for a template for creation """

    await state.clear()  # Clear previous states and data

    kb = choose_template_ikb()
    await msg.answer(l10n.format_value('choose-template'), reply_markup=kb)
    await state.set_state(CreateByTemplate.CHOOSE)


@router.callback_query(
    CreateByTemplate.CHOOSE,
    PaginatorFactory.page_changed()
)
async def change_page_when_choose_template(clb: CallbackQuery, callback_data: PaginatorFactory):
    """ Change page by PaginatorFactory when choose template """

    await clb.answer()
    kb = choose_template_ikb(page=callback_data.page)
    await clb.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(
    CreateByTemplate.CHOOSE,
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
    await state.update_data(template_name=callback_data.name, schema=schema)

    kb = template_properties_ikb(schema, l10n)
    text = get_view_text(schema, {}, l10n)

    await clb.message.edit_text(text=text, reply_markup=kb)
    await state.set_state(CreateByTemplate.VIEW)


@router.callback_query(
    CreateByTemplate.VIEW,
    PaginatorFactory.page_changed()
)
async def change_page_when_choose_property(clb: CallbackQuery, callback_data: PaginatorFactory, state: FSMContext, l10n: FluentLocalization):
    """ Change page by PaginatorFactory when choose property of the template """

    await clb.answer()
    state_data = await state.get_data()
    kb = template_properties_ikb(state_data.get('schema'), l10n, state_data.get('user_data'), page=callback_data.page)
    await clb.message.edit_reply_markup(reply_markup=kb)


@router.callback_query(
    CreateByTemplate.VIEW,
    AskActionFactory.filter()
)
async def select_property(clb: CallbackQuery, callback_data: AskActionFactory, state: FSMContext, l10n: FluentLocalization):
    """ Ask for data for template by clicking on the button """

    # Get schema with properties from state data
    state_data = await state.get_data()
    schema = state_data.get('schema')
    properties = schema.get('properties')

    if callback_data.data not in properties:  # Impossible
        await clb.answer(l10n.format_value('something-went-wrong'), show_alert=True)
        return

    await clb.answer()

    prop: dict = properties[callback_data.data]
    prop["name"] = callback_data.data  # for state_data

    # Remember to update state data with current property
    state_data.update(current_property=prop)
    await state.set_data(state_data)

    # If schema hasn't a question - ask by property name
    text = escape_mdv2(prop.get('question')) if 'question' in prop else f'Введите {callback_data.data}:'

    await clb.message.edit_text(text=text, reply_markup=cancel_ikb(l10n))
    await state.set_state(CreateByTemplate.ADD)


@router.callback_query(
    CreateByTemplate.VIEW,
    F.data == 'generate_document'
)
async def send_document(clb: CallbackQuery, state: FSMContext):
    """ Validate jsonschema and generate document """

    state_data = await state.get_data()
    template_name = state_data.get('template_name')
    schema, user_data = state_data.get('schema'), state_data.get('user_data', {})

    success, error_msg = validate_data(schema, user_data)
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return

    await clb.answer()

    doc = generate_document(template_name, user_data)
    with tempfile.TemporaryDirectory() as tmpdir:
        result_path = Path(tmpdir) / 'result.docx'
        doc.save(result_path)

        # Upload files up to 50 MB
        file = FSInputFile(result_path, filename=f'{schema.get('title')}.docx')
        await clb.message.answer_document(file)


@router.message(CreateByTemplate.ADD)
async def add_property(msg: Message, state: FSMContext, l10n: FluentLocalization):
    """ Add user data to template """

    state_data = await state.get_data()
    prop: dict = state_data.pop('current_property')
    user_data = state_data.get('user_data', {})

    success, error_or_value = validate_property(msg.text, prop, l10n)
    if not success:
        await msg.reply(error_or_value, reply_markup=cancel_ikb(l10n))
        return

    # Update state data
    user_data[prop["name"]] = error_or_value
    state_data['user_data'] = user_data
    await state.set_data(state_data)

    kb = template_properties_ikb(state_data.get('schema'), l10n, user_data)
    text = get_view_text(state_data.get('schema'), user_data, l10n)

    await msg.answer(text=text, reply_markup=kb)
    await state.set_state(CreateByTemplate.VIEW)


@router.callback_query(
    CreateByTemplate.ADD,
    F.data == 'cancel'
)
async def cancel_adding_property(clb: CallbackQuery, state: FSMContext, l10n: FluentLocalization):
    """ Cancel adding property """

    await clb.answer()
    state_data = await state.get_data()

    kb = template_properties_ikb(state_data.get('schema'), l10n, state_data.get('user_data'))
    text = get_view_text(state_data.get('schema'), state_data.get('user_data', {}), l10n)

    await state.set_state(CreateByTemplate.VIEW)
    await clb.message.edit_text(text=text, reply_markup=kb)


# ===== Utils =====
def get_view_text(schema: dict, user_data: dict, l10n: FluentLocalization) -> str:
    text = f'*{escape_mdv2(schema.get('title'))}*\n_{escape_mdv2(schema.get('description'))}_\n\n'
    required = schema.get('required') or []  # required fields

    # Generate text for parameters (properties of template)
    inline_props = []
    for k, prop in schema.get('properties').items():
        inline = f'{prop.get('description')}: `{escape_mdv2(user_data.get(k, ''))}`'
        if k in required:
            inline = fr'*\*{inline}*'

        inline_props.append(inline)

    text += '\n'.join(inline_props) + '\n\n'

    text += fr'_\* \- {l10n.format_value('required-hint')}_'
    return text


def validate_property(value: str, schema: dict, l10n: FluentLocalization) -> tuple[bool, Any]:
    value = value.strip()
    if not value:  # not empty
        return False, l10n.format_value('invalid-input')

    # Validate if type provided
    try:
        match schema.get('type'):
            case 'integer':
                value = int(value)
            case 'number':
                value = float(value)
            case 'boolean':
                value = bool(value)
    except ValueError:
        return False, f'{l10n.format_value('input-type-incorrect')} {schema.get('type')}'

    # Validate if format provided
    try:
        match schema.get('format'):
            case 'date':
                datetime.strptime(value, '%d.%m.%Y')
    except ValueError:
        return False, l10n.format_value('format-type-incorrect')

    return True, value
