from typing import Any

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Button, Back, SwitchTo, Cancel
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession

from database.methods.category import get_categories, create_category, get_category_by_id
from database.methods.item import create_item
from includes.equipment import load_schema, validate_data, create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines import EquipmentAdd
from utils import L10nFormat, escape_mdv2

DIALOG_SCHEMA = 'add_equipment'


def _render_context(context: BaseContext) -> tuple[str, list[tuple[str, str]]]:
    view_lines = []
    data_kb = []

    for key, child in context._children.items():
        if not isinstance(child, PrimitiveContext):
            continue

        value = escape_mdv2(str(child._value)) if child._value is not None else '—'
        description = escape_mdv2(str(child.description))
        required_prefix = r'\* ' if child.required else ''

        view_lines.append(f'{required_prefix}*{description}*: {value}')
        data_kb.append((f'{required_prefix}{description}: {value}', key))

    return '\n'.join(view_lines), data_kb


def _restore_context_data(context: BaseContext, data: dict):
    """Восстанавливает данные в контекст из словаря"""
    for key, value in data.items():
        if key in context._children:
            child = context._children[key]
            if isinstance(child, PrimitiveContext):
                child._value = value


# ========== Окно просмотра ==========
async def get_equipment_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    try:
        schema = load_schema(DIALOG_SCHEMA)
    except FileNotFoundError:
        schema = None

    if not schema:
        return {
            'view': escape_mdv2(l10n.format_value('schema-not-found')),
            'data_kb': [],
            'category_view': escape_mdv2(l10n.format_value('category-view', args={
                'name': '—'
            })),
            'can_submit': False,
            L10N_FORMAT_KEY: l10n,
        }

    # ИСПРАВЛЕНИЕ: create_context принимает только schema, без context_data
    context = create_context(schema)
    
    # Восстанавливаем данные из dialog_data
    context_data = dialog_manager.dialog_data.get('context', {})
    if context_data:
        _restore_context_data(context, context_data)

    view, data_kb = _render_context(context)

    category_name = dialog_manager.dialog_data.get('category_name') or '—'
    category_view = escape_mdv2(l10n.format_value('category-view', args={
        'name': escape_mdv2(str(category_name))
    }))

    return {
        'view': view,
        'data_kb': data_kb,
        'category_view': category_view,
        'can_submit': validate_data(schema, context_data)[0] and bool(dialog_manager.dialog_data.get('category_id')),
        L10N_FORMAT_KEY: l10n,
    }


async def on_data_selected(
    _clb: CallbackQuery,
    _select: Select,
    dialog_manager: DialogManager,
    data: str
):
    dialog_manager.dialog_data.update(current_field=data)
    await dialog_manager.switch_to(EquipmentAdd.ADD)


async def on_submit(
    clb: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    session: AsyncSession = dialog_manager.middleware_data.get('session')

    # Проверка session
    if session is None:
        await clb.answer(l10n.format_value('database-error'), show_alert=True)
        return

    category_id = dialog_manager.dialog_data.get('category_id')
    if not category_id:
        await clb.answer(l10n.format_value('invalid-category'), show_alert=True)
        return

    try:
        schema = load_schema(DIALOG_SCHEMA)
    except FileNotFoundError:
        await clb.answer(l10n.format_value('schema-not-found'), show_alert=True)
        return

    context_data = dialog_manager.dialog_data.get('context', {})
    success, error_msg = validate_data(schema, context_data)
    if not success:
        await clb.answer(error_msg or l10n.format_value('invalid-data'), show_alert=True)
        return

    try:
        item = await create_item(
            session=session,
            name=context_data.get('name', ''),
            category_id=category_id,
            count=context_data.get('count', 0),
            unit=context_data.get('unit', ''),
            description=context_data.get('description', '')
        )

        await clb.message.answer(
            escape_mdv2(l10n.format_value('item-saved', args={
                'name': escape_mdv2(item.name)
            }))
        )
        await dialog_manager.done()

    except Exception as e:
        await clb.message.answer(escape_mdv2(l10n.format_value('item-error')))
        print(f'Error creating item: {e}')


# ========== Окно редактирования ==========
async def get_property_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    current_field = dialog_manager.dialog_data.get('current_field')

    try:
        schema = load_schema(DIALOG_SCHEMA)
    except FileNotFoundError:
        schema = None

    if not schema or not current_field:
        return {
            'question': escape_mdv2(l10n.format_value('field-not-selected')),
            L10N_FORMAT_KEY: l10n,
        }

    # ИСПРАВЛЕНИЕ: create_context принимает только schema
    context = create_context(schema)
    
    # Восстанавливаем данные
    context_data = dialog_manager.dialog_data.get('context', {})
    if context_data:
        _restore_context_data(context, context_data)
    
    child = context._children.get(current_field)

    if isinstance(child, PrimitiveContext):
        field_description = escape_mdv2(str(child.description))
    else:
        field_description = escape_mdv2(str(current_field))

    return {
        'question': escape_mdv2(l10n.format_value('field-input-prompt', args={
            'field': field_description
        })),
        L10N_FORMAT_KEY: l10n,
    }


async def set_property(msg: Message, _: TextInput, dialog_manager: DialogManager, value: str):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    current_field = dialog_manager.dialog_data.get('current_field')

    if not current_field:
        await msg.answer(escape_mdv2(l10n.format_value('field-not-selected')))
        return

    try:
        schema = load_schema(DIALOG_SCHEMA)
    except FileNotFoundError:
        await msg.answer(escape_mdv2(l10n.format_value('schema-not-found')))
        return

    # ИСПРАВЛЕНИЕ: create_context принимает только schema
    context = create_context(schema)
    
    # Восстанавливаем существующие данные
    context_data = dialog_manager.dialog_data.get('context', {})
    if context_data:
        _restore_context_data(context, context_data)

    field_schema = schema.get('properties', {}).get(current_field, {})
    field_type = field_schema.get('type')

    try:
        if field_type == 'integer':
            parsed_value = int(value)
            if parsed_value <= 0:
                await msg.answer(escape_mdv2(l10n.format_value('invalid-number')))
                return
        elif field_type == 'number':
            parsed_value = float(value)
            if parsed_value <= 0:
                await msg.answer(escape_mdv2(l10n.format_value('invalid-number')))
                return
        else:
            parsed_value = value
    except ValueError:
        await msg.answer(escape_mdv2(l10n.format_value('invalid-number')))
        return

    if current_field not in context._children:
        await msg.answer(escape_mdv2(l10n.format_value('field-not-selected')))
        return

    context._children[current_field]._value = parsed_value
    
    # ИСПРАВЛЕНИЕ: Используем get_value() вместо to_dict()
    updated_context_data = context.get_value()
    dialog_manager.dialog_data.update(context=updated_context_data)
    await dialog_manager.switch_to(EquipmentAdd.START)


# ========== Окно выбора категории ==========
async def get_categories_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    session: AsyncSession = dialog_manager.middleware_data.get('session')

    # ИСПРАВЛЕНИЕ: Проверка на None для session
    if session is None:
        return {
            'categories': [],
            L10N_FORMAT_KEY: l10n,
        }

    try:
        categories = await get_categories(session)
        return {
            'categories': [(escape_mdv2(cat.name), str(cat.id)) for cat in categories],
            L10N_FORMAT_KEY: l10n,
        }
    except Exception as e:
        print(f'Error getting categories: {e}')
        return {
            'categories': [],
            L10N_FORMAT_KEY: l10n,
        }


async def on_category_selected(
    clb: CallbackQuery,
    _select: Select,
    dialog_manager: DialogManager,
    category_id: str
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    session: AsyncSession = dialog_manager.middleware_data.get('session')

    # ИСПРАВЛЕНИЕ: Проверка session на None
    if session is None:
        await clb.answer(l10n.format_value('database-error'), show_alert=True)
        return
    
    try:
        category = await get_category_by_id(session, int(category_id))
    except Exception as e:
        print(f'Error getting category: {e}')
        category = None

    if not category:
        await clb.answer(l10n.format_value('invalid-category'), show_alert=True)
        return

    dialog_manager.dialog_data.update(
        category_id=category.id,
        category_name=category.name,
    )

    await clb.answer(escape_mdv2(l10n.format_value('category-selected', args={
        'name': category.name
    })))
    await dialog_manager.switch_to(EquipmentAdd.START)


async def on_create_category_click(
    _clb: CallbackQuery,
    _button: Button,
    dialog_manager: DialogManager
):
    await dialog_manager.switch_to(EquipmentAdd.CREATE_CATEGORY)


# ========== Окно создания категории ==========
async def on_category_name_input(
    msg: Message,
    _: TextInput,
    dialog_manager: DialogManager,
    text: str
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    session: AsyncSession = dialog_manager.middleware_data.get('session')

    # ИСПРАВЛЕНИЕ: Проверка session на None
    if session is None:
        await msg.answer(escape_mdv2(l10n.format_value('database-error')))
        return

    try:
        category = await create_category(session, name=text)

        dialog_manager.dialog_data.update(
            category_id=category.id,
            category_name=category.name,
        )

        await msg.answer(
            escape_mdv2(l10n.format_value('category-created', args={
                'name': escape_mdv2(category.name)
            }))
        )
        await dialog_manager.switch_to(EquipmentAdd.START)

    except Exception as e:
        await msg.answer(escape_mdv2(l10n.format_value('category-error')))
        print(f'Error creating category: {e}')


dialog = Dialog(
    Window(  # Окно просмотра
        Multi(
            L10nFormat('add-equipment-title'),
            Const('\n\n'),
            L10nFormat('welcome-text'),
            Const('\n\n'),
            Format('{view}\n\n'),
            Const(r'_\* \- '),
            L10nFormat('required-hint'),
            Const('_\n\n'),
            Format('{category_view}'),
            sep=''
        ),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='equipment_change',
                item_id_getter=lambda x: x[1],
                items='data_kb',
                on_click=on_data_selected
            ),
            id='equipment_scroll',
            width=1,
            height=6,
            hide_on_single_page=True
        ),
        Row(
            SwitchTo(
                L10nFormat('select-category-btn'),
                id='switch_to_category',
                state=EquipmentAdd.SELECT_CATEGORY,
            ),
        ),
        Row(
            Button(
                L10nFormat('submit-item'),
                id='submit_item',
                on_click=on_submit,
                when=F['can_submit']
            ),
            Cancel(L10nFormat('cancel-button'))
        ),
        getter=get_equipment_context,
        state=EquipmentAdd.START,
        preview_add_transitions=[
            SwitchTo('', '', EquipmentAdd.SELECT_CATEGORY),
            SwitchTo('', '', EquipmentAdd.ADD),
            SwitchTo('', '', EquipmentAdd.CREATE_CATEGORY),
        ]
    ),
    Window(  # Окно редактирования
        Format('{question}'),
        TextInput('input_property', on_success=set_property),
        Back(L10nFormat('back-button')),
        getter=get_property_context,
        state=EquipmentAdd.ADD,
        preview_add_transitions=[Back()]
    ),
    Window(  # Окно выбора категории
        L10nFormat('select-category-prompt'),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='category_select',
                item_id_getter=lambda x: x[1],
                items='categories',
                on_click=on_category_selected
            ),
            id='category_scroll',
            width=1,
            height=8,
            hide_on_single_page=True
        ),
        Row(
            Button(
                L10nFormat('create-new-category-btn'),
                id='create_category',
                on_click=on_create_category_click
            )
        ),
        Back(L10nFormat('back-button')),
        getter=get_categories_data,
        state=EquipmentAdd.SELECT_CATEGORY,
        preview_add_transitions=[
            Back(),
            SwitchTo('', '', EquipmentAdd.CREATE_CATEGORY),
        ]
    ),
    Window(  # Окно создания категории
        L10nFormat('category-name-prompt'),
        TextInput('category_name_input', on_success=on_category_name_input),
        Back(L10nFormat('back-button')),
        state=EquipmentAdd.CREATE_CATEGORY,
        preview_add_transitions=[Back()]
    )
)