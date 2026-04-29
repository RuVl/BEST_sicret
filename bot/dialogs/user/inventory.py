from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Button
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from sqlalchemy import select
from structlog import get_logger
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.models import Category
from middlewares import L10N_FORMAT_KEY
from state_machines.inventory import ViewInventory
from utils import L10nFormat, escape_mdv2, truncate, fuzzy_search
from database.methods import get_all_categories, get_items_by_category, get_item_by_id

# Structlog-логгер для этого модуля
logger: FilteringBoundLogger = get_logger("inventory.view")


# ========== Геттер: список категорий ==========
async def get_categories(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    # Проверяем кэш — если категории уже загружены, не идём в БД
    categories_map: dict = dialog_manager.dialog_data.get('categories_map', {})

    if not categories_map:
        # Кэш пуст — загружаем из БД
        logger.debug("categories_cache_miss", reason="cache empty")
        async with async_session() as session:
            categories = await get_all_categories(session)

        categories_map = {str(c.id): c.name for c in categories}
        dialog_manager.dialog_data['categories_map'] = categories_map
    else:
        logger.debug("categories_cache_hit", count=len(categories_map))

    # Преобразуем словарь в список для виджета
    categories_list = [(name, cid) for cid, name in categories_map.items()]

    return {
        'categories': categories_list,
    }


# ========== Геттер: список айтемов ==========
async def get_items(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    category_id = dialog_manager.dialog_data.get('category_id')
    category_name = dialog_manager.dialog_data.get('category_name', '')

    if not category_id:
        # Не должно происходить — логируем и отправляем назад
        logger.warning("get_items_no_category")
        await dialog_manager.switch_to(ViewInventory.SELECT_CATEGORY)
        return {'items': [], 'items_header': ''}

    async with async_session() as session:
        all_items = await get_items_by_category(session, int(category_id))

    # Формируем список кнопок: "Название | кол-во ед."
    items_list = [
        (f"{truncate(item.name)}  |  {item.count} {item.unit}", str(item.id))
        for item in all_items
    ]

    return {
        'items': items_list,
        # Заголовок окна через l10n
        'items_header': l10n.format_value('items-list', {'category_name': category_name}),
    }


# ========== Геттер: окно поиска ==========
async def get_search(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    category_id = dialog_manager.dialog_data.get('category_id')
    category_name = dialog_manager.dialog_data.get('category_name', '')
    search_query = dialog_manager.dialog_data.get('search_query', '')

    if not category_id:
        logger.warning("get_search_no_category")
        await dialog_manager.switch_to(ViewInventory.SELECT_CATEGORY)
        return {'items': [], 'items_header': '', 'search_hint': ''}

    async with async_session() as session:
        all_items = await get_items_by_category(session, int(category_id))

    if search_query:
        # Передаём список имён в fuzzy_search — он работает со списком строк
        names = [item.name for item in all_items]
        matched_names = fuzzy_search(search_query, names)

        # Фильтруем объекты по совпавшим именам, сохраняя порядок
        name_to_items = {item.name: item for item in all_items}
        matched_items = [name_to_items[name] for name in matched_names if name in name_to_items]

        search_hint = l10n.format_value('search-result', {
            'query': search_query,
            'count': len(matched_items),
        })
        logger.debug("fuzzy_search_done", query=search_query, found=len(matched_items))
    else:
        matched_items = all_items
        search_hint = l10n.format_value('search-hint')

    items_list = [
        (f"{truncate(item.name)}  |  {item.count} {item.unit}", str(item.id))
        for item in matched_items
    ]

    return {
        'items': items_list,
        'items_header': l10n.format_value('items-list', {'category_name': category_name}),
        'search_hint': search_hint,
    }


# ========== Геттер: детали айтема ==========
async def get_item_detail(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    item_id = dialog_manager.dialog_data.get('item_id')

    if not item_id:
        logger.warning("get_item_detail_no_id")
        await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)
        return {'item_text': ''}

    async with async_session() as session:
        item = await get_item_by_id(session, int(item_id))

    if not item:
        logger.warning("get_item_detail_not_found", item_id=item_id)
        await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)
        return {'item_text': ''}

    no_place = l10n.format_value('no-place')
    place_address = item.place.address if item.place else no_place

    # Формируем текст карточки через l10n с экранированием спецсимволов
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

    # Ищем имя категории в кэше (словарь, без цикла)
    categories_map: dict = dialog_manager.dialog_data.get('categories_map', {})
    category_name = categories_map.get(category_id)

    if not category_name:
        # Кэш промахнулся — идём в БД
        logger.warning("category_cache_miss_on_select", category_id=category_id)
        async with async_session() as session:
            query = select(Category).where(Category.id == int(category_id))
            result = await session.execute(query)
            cat = result.scalar_one_or_none()

        if not cat:
            # Категория не найдена вообще — сбрасываем
            logger.error("category_not_found_in_db", category_id=category_id)
            await clb.answer(l10n.format_value('category-not-found'))
            await dialog_manager.switch_to(ViewInventory.SELECT_CATEGORY)
            return

        category_name = cat.name

    dialog_manager.dialog_data['category_id'] = category_id
    dialog_manager.dialog_data['category_name'] = category_name
    # Сбрасываем поиск при смене категории
    dialog_manager.dialog_data['search_query'] = ''

    await clb.answer()
    await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)


# ========== Хэндлер: переход в окно поиска ==========
async def on_open_search(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
):
    # Сбрасываем предыдущий запрос при открытии поиска
    dialog_manager.dialog_data['search_query'] = ''
    await callback.answer()
    await dialog_manager.switch_to(ViewInventory.SEARCH_ITEM)


# ========== Хэндлер: ввод поискового запроса ==========
async def on_search_input(
    message: Message,
    widget: TextInput,
    dialog_manager: DialogManager,
    text: str,
):
    # Сохраняем запрос — геттер перерисует список
    dialog_manager.dialog_data['search_query'] = text.strip()


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


# ========== Хэндлер: назад к списку айтемов ==========
async def on_back_to_items(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
):
    dialog_manager.dialog_data.pop('item_id', None)
    await callback.answer()
    await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)


# ========== Хэндлер: назад из поиска к списку ==========
async def on_back_from_search(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager,
):
    dialog_manager.dialog_data.pop('search_query', None)
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

    # --- Окно 2: список айтемов (без поиска) ---
    Window(
        Format('{items_header}'),
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
        # Кнопка перехода в отдельное окно поиска
        Button(
            L10nFormat('search'),
            id='open_search',
            on_click=on_open_search,
        ),
        Button(
            L10nFormat('back'),
            id='back_to_cats',
            on_click=on_back_to_categories,
        ),
        getter=get_items,
        state=ViewInventory.SELECT_ITEM,
    ),

    # --- Окно 3: поиск (отдельное окно, без смешения логики) ---
    Window(
        Format('{items_header}\n\n{search_hint}'),
        # Поле ввода поискового запроса
        TextInput(
            id='search_input',
            on_success=on_search_input,
        ),
        ScrollingGroup(
            Select(
                Format('{item[0]}'),
                id='search_item_select',
                item_id_getter=lambda x: x[1],
                items='items',
                on_click=on_item_selected,
            ),
            id='search_items_scroll',
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        Button(
            L10nFormat('back'),
            id='back_from_search',
            on_click=on_back_from_search,
        ),
        getter=get_search,
        state=ViewInventory.SEARCH_ITEM,
    ),

    # --- Окно 4: детали айтема ---
    Window(
        Format('{item_text}'),
        Button(
            L10nFormat('back'),
            id='back_to_items',
            on_click=on_back_to_items,
        ),
        getter=get_item_detail,
        state=ViewInventory.VIEW_ITEM,
    ),
)