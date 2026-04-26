from typing import Any
import logging

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Button
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from sqlalchemy import select

from database.main import async_session
from database.models import Category
from middlewares import L10N_FORMAT_KEY
from state_machines.inventory import ViewInventory
from utils import L10nFormat, escape_mdv2
from database.methods import get_all_categories, get_items_by_category, get_item_by_id

logger = logging.getLogger(__name__)


# ========= НЕЧЁТКИЙ ПОИСК =========
def fuzzy_match(query: str, text: str) -> bool:
    query = query.lower().strip()
    text = text.lower()
    it = iter(text)
    return all(ch in it for ch in query)


def fuzzy_score(query: str, text: str) -> int:
    query = query.lower().strip()
    text = text.lower()
    if query in text:
        return 0
    return len(text)


def truncate(text: str, max_len: int = 15) -> str:
    return text[:max_len] + '…' if len(text) > max_len else text


# ========== Геттер: список категорий ==========
async def get_categories(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    async with async_session() as session:
        categories = await get_all_categories(session)

    categories_map = {str(c.id): c.name for c in categories}
    categories_list = [(c.name, str(c.id)) for c in categories]

    dialog_manager.dialog_data['categories_map'] = categories_map

    return {
        'categories': categories_list,
    }


# ========== Геттер: список айтемов (с фильтром) ==========
async def get_items(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    category_id = dialog_manager.dialog_data.get('category_id')
    category_name = dialog_manager.dialog_data.get('category_name', '')
    search_query = dialog_manager.dialog_data.get('search_query', '')

    if not category_id:
        logger.warning("get_items вызван без category_id, переключаемся на выбор категории")
        await dialog_manager.switch_to(ViewInventory.SELECT_CATEGORY)
        return {'items': [], 'items_header': '', 'search_hint': '', 'has_search': False}

    async with async_session() as session:
        all_items = await get_items_by_category(session, int(category_id))

    if search_query:
        matched = [item for item in all_items if fuzzy_match(search_query, item.name)]
        matched.sort(key=lambda item: fuzzy_score(search_query, item.name))
        search_hint = l10n.format_value('search-result', {
            'query': search_query,
            'count': len(matched),
        })
    else:
        matched = all_items
        search_hint = l10n.format_value('search-hint')

    items_list = [
        (f"{truncate(item.name)}  |  {item.count} {item.unit}", str(item.id))
        for item in matched
    ]

    return {
        'items': items_list,
        'items_header': l10n.format_value('items-list', {'category_name': category_name}),
        'search_hint': search_hint,
        'has_search': bool(search_query),
    }


# ========== Геттер: детали айтема ==========
async def get_item_detail(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    item_id = dialog_manager.dialog_data.get('item_id')

    if not item_id:
        logger.warning("get_item_detail вызван без item_id, переключаемся на список товаров")
        await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)
        return {'item_text': ''}

    async with async_session() as session:
        item = await get_item_by_id(session, int(item_id))

    if not item:
        logger.warning("Товар id=%s не найден в БД, переключаемся на список товаров", item_id)
        await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)
        return {'item_text': ''}

    no_place = l10n.format_value('no-place')
    place_address = item.place.address if item.place else no_place

    item_text = l10n.format_value('item-detail', {
        'name': escape_mdv2(item.name),
        'count': item.count,
        'unit': escape_mdv2(item.unit),
        'address': escape_mdv2(place_address),
    })

    return {'item_text': item_text}


# ========== Хэндлер: выбор категории ==========
async def on_category_selected(
    clb: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    category_id: str,
):
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    categories_map: dict = dialog_manager.dialog_data.get('categories_map', {})
    category_name = categories_map.get(category_id)

    if not category_name:
        logger.warning("Категория id=%s не найдена в кэше, запрашиваем из БД", category_id)
        async with async_session() as session:
            query = select(Category).where(Category.id == int(category_id))
            result = await session.execute(query)
            cat = result.scalar_one_or_none()

        if not cat:
            logger.error("Категория id=%s не найдена в БД, сбрасываем на выбор категории", category_id)
            await clb.answer(l10n.format_value('category-not-found'))
            await dialog_manager.switch_to(ViewInventory.SELECT_CATEGORY)
            return

        category_name = cat.name

    dialog_manager.dialog_data['category_id'] = category_id
    dialog_manager.dialog_data['category_name'] = category_name
    dialog_manager.dialog_data['search_query'] = ''

    await clb.answer()
    await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)


# ========== Хэндлер: поисковый запрос ==========
async def on_search_input(
    message: Message,
    widget: TextInput,
    dialog_manager: DialogManager,
    text: str,
):
    dialog_manager.dialog_data['search_query'] = text.strip()


# ========== Хэндлер: сброс поиска ==========
async def on_clear_search(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
):
    dialog_manager.dialog_data['search_query'] = ''
    await callback.answer()


# ========== Хэндлер: выбор айтема ==========
async def on_item_selected(
    clb: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
):
    dialog_manager.dialog_data['item_id'] = item_id
    await clb.answer()
    await dialog_manager.switch_to(ViewInventory.VIEW_ITEM)


# ========== Хэндлер: назад к категориям ==========
async def on_back_to_categories(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
):
    dialog_manager.dialog_data.pop('category_id', None)
    dialog_manager.dialog_data.pop('category_name', None)
    dialog_manager.dialog_data.pop('search_query', None)
    await callback.answer()
    await dialog_manager.switch_to(ViewInventory.SELECT_CATEGORY)


# ========== Хэндлер: назад к айтемам ==========
async def on_back_to_items(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
):
    dialog_manager.dialog_data.pop('item_id', None)
    await callback.answer()
    await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)


# ========== Диалог ==========
inventory_dialog = Dialog(
    # --- Окно 1: выбор категории ---
    Window(
        L10nFormat('choose-category'),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='category_select',
                item_id_getter=lambda x: x[1],
                items='categories',
                on_click=on_category_selected,
            ),
            id='category_scroll',
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        getter=get_categories,
        state=ViewInventory.SELECT_CATEGORY,
    ),

    # --- Окно 2: список айтемов + поиск ---
    Window(
        Format('{items_header}\n\n{search_hint}'),
        TextInput(
            id='search_input',
            on_success=on_search_input,
        ),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='item_select',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=on_item_selected,
            ),
            id='items_scroll',
            width=1,
            height=10,
            hide_on_single_page=True,
        ),
        Button(
            L10nFormat('clear-search'),
            id='clear_search',
            on_click=on_clear_search,
            when='has_search',
        ),
        Button(
            L10nFormat('back'),
            id='back_to_cats',
            on_click=on_back_to_categories,
        ),
        getter=get_items,
        state=ViewInventory.SELECT_ITEM,
    ),

    # --- Окно 3: детали айтема ---
    Window(
        Format('{item_text}'),
        Button(
            L10nFormat('back'),
            id='back_to_items',
            on_click=on_back_to_items,
        ),
        getter=get_item_detail,
        state=ViewInventory.VIEW_ITEM,
        parse_mode='MarkdownV2',
    ),
)