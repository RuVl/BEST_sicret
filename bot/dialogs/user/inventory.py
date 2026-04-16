from typing import Any
import re

from aiogram.types import CallbackQuery
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Button
from aiogram_dialog.widgets.text import Format
from fluent.runtime import FluentLocalization
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database.main import async_session
from database.models import Category, Item
from middlewares import L10N_FORMAT_KEY
from state_machines.inventory import ViewInventory
from utils import L10nFormat


# ========= ЭКРАНИРОВАНИЕ MarkdownV2 =========
def escape_md(text: str) -> str:
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!])', r'\\\1', str(text))


# ========== Геттер для окна категорий ==========
async def get_categories(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    async with async_session() as session:
        result = await session.execute(select(Category))
        categories = result.scalars().all()

    categories_list = [(c.name, str(c.id)) for c in categories]
    dialog_manager.dialog_data['categories'] = categories_list

    return {
        'categories': categories_list,
        'has_categories': len(categories_list) > 0
    }


# ========== Геттер для окна товаров ==========
async def get_items(dialog_manager: DialogManager, **kwargs) -> dict[str, Any]:
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)

    category_id = dialog_manager.dialog_data.get('category_id')
    category_name = dialog_manager.dialog_data.get('category_name')

    if not category_id:
        return {'items_text': 'Категория не выбрана'}

    async with async_session() as session:
        result = await session.execute(
            select(Item)
            .where(Item.category_id == int(category_id))
            .options(selectinload(Item.place))
        )
        items = result.scalars().all()

    if items:
        items_text = f" Товары в категории \"{escape_md(category_name)}\":\n\n"

        for item in items:
            place_address = item.place.address if item.place else "Место не указано"

            items_text += (
                f" {escape_md(item.name)}, количество: {item.count} {escape_md(item.unit)}\n"
                f"адрес:  {escape_md(place_address)}\n\n"
            )
    else:
        items_text = f"В категории \"{escape_md(category_name)}\" нет товаров"

    return {'items_text': items_text}


# ========== Хэндлер выбора категории ==========
async def on_category_selected(
    clb: CallbackQuery,
    widget: Select,
    dialog_manager: DialogManager,
    category_id: str
):
    categories = dialog_manager.dialog_data.get('categories', [])

    category_name = None
    for name, cid in categories:
        if cid == category_id:
            category_name = name
            break

    if not category_name:
        async with async_session() as session:
            result = await session.execute(
                select(Category).where(Category.id == int(category_id))
            )
            category = result.scalar_one_or_none()
            category_name = category.name if category else "Неизвестная категория"

    dialog_manager.dialog_data['category_id'] = category_id
    dialog_manager.dialog_data['category_name'] = category_name

    await dialog_manager.switch_to(ViewInventory.VIEW_ITEMS)
    await clb.answer()


# ========== Назад ==========
async def on_back_to_categories(
    callback: CallbackQuery,
    button: Button,
    dialog_manager: DialogManager
):
    dialog_manager.dialog_data.pop('category_id', None)
    dialog_manager.dialog_data.pop('category_name', None)

    await dialog_manager.switch_to(ViewInventory.VIEW_CATEGORIES)
    await callback.answer()


# ========== Диалог ==========
inventory_dialog = Dialog(
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
        state=ViewInventory.VIEW_CATEGORIES,
    ),
    Window(
        Format('{items_text}'),
        Button(
            L10nFormat('back'),
            id='back_btn',
            on_click=on_back_to_categories,
        ),
        getter=get_items,
        state=ViewInventory.VIEW_ITEMS,
    ),
)