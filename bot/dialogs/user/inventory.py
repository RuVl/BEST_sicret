from operator import attrgetter
from typing import Any

from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, DialogManager, Window
from aiogram_dialog.widgets.input import ManagedTextInput, TextInput
from aiogram_dialog.widgets.kbd import Back, Button, ScrollingGroup, Select
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from structlog.typing import FilteringBoundLogger

from database.main import async_session
from database.methods.category import get_categories
from database.methods.item import get_item_with_place, get_items_by_category_id
from state_machines.inventory import ViewInventory
from utils import escape_mdv2, fuzzy_search_bests, L10nFormat, truncate

BTN_TRUNCATE_LEN = 25


# ========== Геттер: список категорий ==========
async def get_categories_data(
    dialog_manager: DialogManager,
    **kwargs,
) -> dict[str, Any]:
    categories_map = dialog_manager.dialog_data.get("categories_map", {})

    if not categories_map:
        async with async_session() as session:
            categories = await get_categories(session)

        categories_map = {c.id: c.name for c in categories}
        dialog_manager.dialog_data["categories_map"] = categories_map

    is_selection_mode = (
        dialog_manager.start_data.get("selection_mode", False)
        if dialog_manager.start_data
        else False
    )

    return {
        "categories": categories_map.items(),
        "is_selection_mode": is_selection_mode,
    }


# ========== Геттер: окно поиска ==========
async def get_items_data(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    **kwargs,
) -> dict[str, Any]:
    category_id = int(dialog_manager.dialog_data["category_id"])
    category_name = dialog_manager.dialog_data["category_name"]
    search_query = dialog_manager.dialog_data.get("search_query")

    async with async_session() as session:
        all_items = await get_items_by_category_id(session, category_id)

    if search_query:
        matched_items = fuzzy_search_bests(
            search_query,
            all_items,
            extractor=attrgetter("name"),
        )
        search_hint = l10n.format_value(
            "search-result",
            args={
                "query": escape_mdv2(search_query),
                "count": len(matched_items),
            },
        )
    else:
        matched_items = all_items
        search_hint = l10n.format_value("search-hint")

    header_text = l10n.format_value(
        "items-list",
        args={"category_name": category_name},
    )
    items_list = [
        (item.id, f"{truncate(item.name, BTN_TRUNCATE_LEN)} | {item.count} {item.unit}")
        for item in matched_items
    ]

    return {
        "text": header_text,
        "hint": search_hint,
        "items": items_list,
        "search_query": search_query,
    }


# ========== Геттер: детали айтема ==========
async def get_item_detail(
    dialog_manager: DialogManager,
    l10n: FluentLocalization,
    log: FilteringBoundLogger,
    **kwargs,
) -> dict[str, Any]:
    item_id = int(dialog_manager.dialog_data["item_id"])

    async with async_session() as session:
        item = await get_item_with_place(session, item_id)

    if not item:
        await log.aerror("get_item_detail: Item not found", item_id=item_id)
        await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)
        return {}

    place_address = item.place.address if item.place else l10n.format_value("no-place")

    item_text = l10n.format_value(
        "item-detail",
        {
            "name": escape_mdv2(item.name),
            "count": item.count,
            "unit": escape_mdv2(item.unit),
            "address": escape_mdv2(place_address),
        },
    )

    is_selection_mode = (
        dialog_manager.start_data.get("selection_mode", False)
        if dialog_manager.start_data
        else False
    )

    return {
        "item_text": item_text,
        "is_selection_mode": is_selection_mode,
    }


# ========== Хэндлер: выбор категории ==========
async def on_category_selected(
    clb: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    category_id: int,
) -> None:
    categories_map: dict[int, str] = dialog_manager.dialog_data["categories_map"]
    category_name = categories_map.get(category_id)

    dialog_manager.dialog_data.update(
        category_id=category_id,
        category_name=category_name,
        search_query="",
    )
    await dialog_manager.switch_to(ViewInventory.SELECT_ITEM)


# ========== Хэндлер: ввод поискового запроса ==========
async def on_search_input(
    msg: Message,
    widget: ManagedTextInput[str],
    dialog_manager: DialogManager,
    text: str,
) -> None:
    dialog_manager.dialog_data["search_query"] = text.strip()


# ========== Хэндлер: очистка поискового запроса ==========
async def clear_search(
    clb: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    dialog_manager.dialog_data.pop("search_query", None)


# ========== Хэндлер: выбор айтема ==========
async def on_item_selected(
    clb: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    item_id: str,
) -> None:
    dialog_manager.dialog_data["item_id"] = item_id
    await dialog_manager.switch_to(ViewInventory.VIEW_ITEM)


# ========== Хэндлер: выбор айтема (финальный в режиме выбора) ==========
async def on_item_chosen(
    clb: CallbackQuery,
    widget: Button,
    dialog_manager: DialogManager,
) -> None:
    item_id = dialog_manager.dialog_data["item_id"]
    # We need to get name and unit too. We can get it from the getter or just re-fetch.
    # Actually, it's better to fetch it here or have it in dialog_data.
    async with async_session() as session:
        item = await get_item_with_place(session, int(item_id))

    if item:
        await dialog_manager.done(
            result={
                "item_id": item.id,
                "name": item.name,
                "unit": item.unit,
                "count": item.count,
            },
        )
    else:
        await clb.answer("Item not found", show_alert=True)


# ========== Диалог ==========
inventory_dialog = Dialog(
    # --- Окно 1: выбор Category ---
    Window(
        L10nFormat("choose-category"),
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="category_select",
                item_id_getter=lambda x: x[0],
                items="categories",
                type_factory=int,
                on_click=on_category_selected,
            ),
            id="categories_scroll",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        Button(
            L10nFormat("cancel"),
            id="cancel_inventory",
            on_click=lambda c, b, m: m.done(),
            when="is_selection_mode",
        ),
        getter=get_categories_data,
        state=ViewInventory.SELECT_CATEGORY,
    ),
    # --- Окно 2: список Item с поиском ---
    Window(
        Format("{text}\n{hint}"),
        TextInput(
            id="search_input",
            on_success=on_search_input,
        ),
        ScrollingGroup(
            Select(
                Format("{item[1]}"),
                id="item_select",
                item_id_getter=lambda x: x[0],
                items="items",
                on_click=on_item_selected,
            ),
            id="items_scroll",
            width=1,
            height=8,
            hide_on_single_page=True,
        ),
        Button(
            L10nFormat("clear-search"),
            id="clear_search",
            on_click=clear_search,
            when="search_query",
        ),
        Back(L10nFormat("back")),
        getter=get_items_data,
        state=ViewInventory.SELECT_ITEM,
    ),
    # --- Окно 3: детали Item ---
    Window(
        Format("{item_text}"),
        Button(
            L10nFormat("select-item"),
            id="select_item_btn",
            on_click=on_item_chosen,
            when="is_selection_mode",
        ),
        Back(L10nFormat("back")),
        getter=get_item_detail,
        state=ViewInventory.VIEW_ITEM,
    ),
)
