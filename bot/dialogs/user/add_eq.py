import logging
from copy import deepcopy
from typing import Any

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Button, SwitchTo, Cancel, Start
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization

from database.main import async_session
from database.methods.category import get_categories, get_category_by_id
from database.methods.item import create_item
from database.methods.item import get_places, get_place_by_id
from includes import load_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines import EquipmentAdd, CategoryCreate
from utils import L10nFormat, escape_mdv2

logger = logging.getLogger(__name__)

DIALOG_SCHEMA = 'equipments/add_equipment.json'


def _clean_context_data(data: dict) -> dict:
    """Убирает None и пустые строки"""
    return {
        k: v for k, v in data.items()
        if v is not None and v != ''
    }


def _get_place_title(place: Any) -> str:
    for attr in ('name', 'title', 'address'):
        value = getattr(place, attr, None)
        if value:
            return str(value)
    return f'ID {getattr(place, "id", "")}'


def _build_context(dialog_manager: DialogManager, schema: dict) -> BaseContext:
    """Создаёт контекст и восстанавливает в него сохранённые данные"""
    context = create_context(deepcopy(schema))
    context_data = _clean_context_data(dialog_manager.dialog_data.get('context', {}))
    if context_data:
        _restore_context_data(context, context_data)
    return context


def _render_context(context: BaseContext, l10n: FluentLocalization) -> tuple[str, list[tuple[str, str]]]:
    view_lines = []
    data_kb = []
    empty = l10n.format_value('empty-value')

    for key, child in context._children.items():
        if not isinstance(child, PrimitiveContext):
            continue

        value = escape_mdv2(str(child._value)) if child._value is not None else empty
        description = str(child.description)
        required_prefix = r'\* ' if child.required else ''

        view_lines.append(f'{required_prefix}*{description}*: {value}')
        data_kb.append((f'{required_prefix}{description}: {value}', key))

    return '\n'.join(view_lines), data_kb


def _restore_context_data(context: BaseContext, data: dict):
    # Using internal context fields because BaseContext API
    # does not expose flat-form field restoration needed for this dialog.
    for key, value in data.items():
        if key in context._children:
            child = context._children[key]
            if isinstance(child, PrimitiveContext):
                child._value = value


# ========== Обработка результата из дочернего диалога ==========
async def on_process_result(start_data: Any, result: Any, dialog_manager: DialogManager):
    if result and isinstance(result, dict):
        if 'category_id' in result:
            dialog_manager.dialog_data.update(
                category_id=result['category_id'],
                category_name=result['category_name'],
            )


# ========== Окно просмотра ==========
async def get_equipment_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    empty = l10n.format_value('empty-value')

    try:
        schema = load_schema(DIALOG_SCHEMA)
    except FileNotFoundError:
        logger.warning("Schema '%s' not found", DIALOG_SCHEMA)
        return {
            'view': escape_mdv2(l10n.format_value('schema-not-found')),
            'data_kb': [],
            'category_view': rf'*{l10n.format_value("category-label")}*: {empty}',
            'place_view': rf'*{l10n.format_value("place-label")}*: {empty}',
            'can_submit': False,
            L10N_FORMAT_KEY: l10n,
        }

    context = _build_context(dialog_manager, schema)
    view, data_kb = _render_context(context, l10n)

    context_data = _clean_context_data(dialog_manager.dialog_data.get('context', {}))
    category_name = dialog_manager.dialog_data.get('category_name') or empty
    place_name = dialog_manager.dialog_data.get('place_name') or empty

    can_submit, _ = validate_data(schema, context_data)

    return {
        'view': view,
        'data_kb': data_kb,
        'category_view': rf'*{l10n.format_value("category-label")}*: {escape_mdv2(str(category_name))}',
        'place_view': rf'*{l10n.format_value("place-label")}*: {escape_mdv2(str(place_name))}',
        'can_submit': (
            can_submit
            and bool(dialog_manager.dialog_data.get('category_id'))
            and bool(dialog_manager.dialog_data.get('place_id'))
        ),
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

    category_id = dialog_manager.dialog_data.get('category_id')
    place_id = dialog_manager.dialog_data.get('place_id')

    if not category_id:
        await clb.answer(l10n.format_value('invalid-category'), show_alert=True)
        return

    if not place_id:
        await clb.answer(l10n.format_value('invalid-place'), show_alert=True)
        return

    try:
        schema = load_schema(DIALOG_SCHEMA)
    except FileNotFoundError:
        await clb.answer(l10n.format_value('schema-not-found'), show_alert=True)
        return

    context_data = _clean_context_data(dialog_manager.dialog_data.get('context', {}))
    success, error_msg = validate_data(schema, context_data)
    if not success:
        await clb.answer(error_msg or l10n.format_value('invalid-data'), show_alert=True)
        return

    try:
        async with async_session() as session:
            item = await create_item(
                session=session,
                name=context_data['name'],
                category_id=category_id,
                count=context_data['count'],
                unit=context_data['unit'],
                place_id=place_id,
            )

        await clb.message.answer(
            escape_mdv2(l10n.format_value('item-saved', args={'name': item.name}))
        )
        await dialog_manager.done()

    except Exception:
        logger.exception("Error creating item")
        await clb.message.answer(escape_mdv2(l10n.format_value('item-error')))


# ========== Окно редактирования ==========
async def get_property_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    current_field = dialog_manager.dialog_data.get('current_field')

    try:
        schema = load_schema(DIALOG_SCHEMA)
    except FileNotFoundError:
        logger.warning("Schema '%s' not found", DIALOG_SCHEMA)
        schema = None

    if not schema or not current_field:
        return {
            'question': escape_mdv2(l10n.format_value('field-not-selected')),
            L10N_FORMAT_KEY: l10n,
        }

    context = _build_context(dialog_manager, schema)
    child = context._children.get(current_field)

    if isinstance(child, PrimitiveContext):
        field_description = str(child.description)
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

    context = _build_context(dialog_manager, schema)

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
            parsed_value = value.strip()
            if not parsed_value:
                await msg.answer(escape_mdv2(l10n.format_value('field-empty-error')))
                return
    except ValueError:
        await msg.answer(escape_mdv2(l10n.format_value('invalid-number')))
        return

    if current_field not in context._children:
        await msg.answer(escape_mdv2(l10n.format_value('field-not-selected')))
        return

    context._children[current_field]._value = parsed_value

    updated_context_data = _clean_context_data(context.get_value())
    dialog_manager.dialog_data.update(context=updated_context_data)
    await dialog_manager.switch_to(EquipmentAdd.START)


# ========== Окно выбора категории ==========
async def get_categories_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    try:
        async with async_session() as session:
            categories = await get_categories(session)
        return {
            'categories': [(escape_mdv2(cat.name), str(cat.id)) for cat in categories],
            L10N_FORMAT_KEY: l10n,
        }
    except Exception:
        logger.exception("Error getting categories")
        return {'categories': [], L10N_FORMAT_KEY: l10n}


async def on_category_selected(
    clb: CallbackQuery,
    _select: Select,
    dialog_manager: DialogManager,
    category_id: str
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    try:
        async with async_session() as session:
            category = await get_category_by_id(session, int(category_id))
    except Exception:
        logger.exception("Error getting category id=%s", category_id)
        category = None

    if not category:
        await clb.answer(l10n.format_value('category-invalid'), show_alert=True)
        return

    dialog_manager.dialog_data.update(
        category_id=category.id,
        category_name=category.name,
    )

    await clb.answer(l10n.format_value('category-selected', args={'name': category.name}))
    await dialog_manager.switch_to(EquipmentAdd.START)


# ========== Окно выбора места ==========
async def get_places_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    try:
        async with async_session() as session:
            places = await get_places(session)
        return {
            'places': [
                (escape_mdv2(_get_place_title(p)), str(p.id))
                for p in places
            ],
            L10N_FORMAT_KEY: l10n,
        }
    except Exception:
        logger.exception("Error getting places")
        return {'places': [], L10N_FORMAT_KEY: l10n}


async def on_place_selected(
    clb: CallbackQuery,
    _select: Select,
    dialog_manager: DialogManager,
    place_id: str
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    try:
        async with async_session() as session:
            place = await get_place_by_id(session, int(place_id))
    except Exception:
        logger.exception("Error getting place id=%s", place_id)
        place = None

    if not place:
        await clb.answer(l10n.format_value('place-invalid'), show_alert=True)
        return

    place_title = _get_place_title(place)

    dialog_manager.dialog_data.update(
        place_id=place.id,
        place_name=place_title,
    )

    await clb.answer(l10n.format_value('place-selected', args={'name': place_title}))
    await dialog_manager.switch_to(EquipmentAdd.START)


# ========== Dialog ==========
dialog = Dialog(
    Window(
        Multi(
            L10nFormat('add-equipment-title'),
            Const('\n\n'),
            L10nFormat('welcome-text'),
            Const('\n\n'),
            Format('{view}\n\n'),
            L10nFormat('required-hint'),
            Format('{category_view}\n'),
            Format('{place_view}'),
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
            SwitchTo(
                L10nFormat('select-place-btn'),
                id='switch_to_place',
                state=EquipmentAdd.SELECT_PLACE,
            ),
        ),
        Row(
            Start(
                L10nFormat('create-new-category-btn'),
                id='start_create_category',
                state=CategoryCreate.INPUT_NAME,
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
            SwitchTo('', '', EquipmentAdd.SELECT_PLACE),
            SwitchTo('', '', EquipmentAdd.ADD),
        ]
    ),
    Window(
        Format('{question}'),
        TextInput('input_property', on_success=set_property),
        SwitchTo(
            L10nFormat('back-button'),
            id='back_from_add',
            state=EquipmentAdd.START,
        ),
        getter=get_property_context,
        state=EquipmentAdd.ADD,
    ),
    Window(
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
        SwitchTo(
            L10nFormat('back-button'),
            id='back_from_category',
            state=EquipmentAdd.START,
        ),
        getter=get_categories_data,
        state=EquipmentAdd.SELECT_CATEGORY,
    ),
    Window(
        L10nFormat('select-place-prompt'),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='place_select',
                item_id_getter=lambda x: x[1],
                items='places',
                on_click=on_place_selected
            ),
            id='place_scroll',
            width=1,
            height=8,
            hide_on_single_page=True
        ),
        SwitchTo(
            L10nFormat('back-button'),
            id='back_from_place',
            state=EquipmentAdd.START,
        ),
        getter=get_places_data,
        state=EquipmentAdd.SELECT_PLACE,
    ),
    on_process_result=on_process_result,
)