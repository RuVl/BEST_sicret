from typing import Any, Dict, List

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Button, Back, SwitchTo
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization
from sqlalchemy.ext.asyncio import AsyncSession

from database.methods.application import create_application
from database.methods.category import get_all_categories, get_category_by_id
from database.methods.item import get_items_by_category_id, get_item_by_id
from database.methods.person import get_person_by_telegram_id
from env import TelegramKeys
from filters import get_session_from_dialog_manager
from middlewares import L10N_FORMAT_KEY, SESSION_KEY
from state_machines.property_database import PropertyDatabase
from utils import L10nFormat, escape_mdv2


# ========== Главное меню ==========
async def get_main_menu_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_show_list_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к выбору категории для просмотра списка """
    await dialog_manager.switch_to(PropertyDatabase.SHOW_LIST_CATEGORY)


async def on_create_application_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к форме создания заявки """
    # Инициализируем данные заявки
    dialog_manager.dialog_data.update(
        applicant_name=None,
        purpose=None,
        selected_items={}  # {item_id: quantity}
    )
    await dialog_manager.switch_to(PropertyDatabase.CREATE_APPLICATION)


# ========== Выбор категории для просмотра списка ==========
async def get_categories_list(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает список всех категорий """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    categories = await get_all_categories(session)
    return {'categories': categories}


async def on_category_selected_for_list(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, category_id: str):
    """ Сохраняет выбранную категорию и переходит к списку предметов """
    dialog_manager.dialog_data['selected_category_id'] = int(category_id)
    await dialog_manager.switch_to(PropertyDatabase.SHOW_LIST_ITEMS)


# ========== Список предметов категории ==========
async def get_items_list(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает список предметов выбранной категории """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    category_id = dialog_manager.dialog_data.get('selected_category_id')
    
    if not category_id:
        return {'items_text': 'Категория не выбрана', 'category_name': ''}
    
    category = await get_category_by_id(session, category_id)
    items = await get_items_by_category_id(session, category_id)
    
    # Форматируем список для отображения
    items_list = []
    for item in items:
        items_list.append(f"{item.name} - {item.count} {item.unit}")
    
    items_text = "\n".join(items_list) if items_list else "Нет доступных предметов"
    
    return {
        'items_text': items_text,
        'category_name': category.name if category else ''
    }


# ========== Форма создания заявки ==========
async def get_application_form_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные формы заявки """
    applicant_name = dialog_manager.dialog_data.get('applicant_name', 'Не заполнено')
    purpose = dialog_manager.dialog_data.get('purpose', 'Не заполнено')
    selected_items = dialog_manager.dialog_data.get('selected_items', {})
    
    items_count = len(selected_items)
    items_text = f"{items_count} предмет(ов)" if items_count > 0 else "Не выбрано"
    
    return {
        'applicant_name': applicant_name,
        'purpose': purpose,
        'items_text': items_text
    }


async def on_name_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу имени """
    await dialog_manager.switch_to(PropertyDatabase.INPUT_NAME)


async def on_purpose_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к вводу цели """
    await dialog_manager.switch_to(PropertyDatabase.INPUT_PURPOSE)


async def on_items_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к выбору предметов """
    await dialog_manager.switch_to(PropertyDatabase.SELECT_ITEMS)


async def on_review_clicked(_clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Переход к просмотру заявки """
    # Проверяем, что все поля заполнены
    applicant_name = dialog_manager.dialog_data.get('applicant_name')
    purpose = dialog_manager.dialog_data.get('purpose')
    selected_items = dialog_manager.dialog_data.get('selected_items', {})
    
    if not applicant_name or not purpose or not selected_items:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await _clb.answer("Пожалуйста, заполните все поля", show_alert=True)
        return
    
    await dialog_manager.switch_to(PropertyDatabase.REVIEW_APPLICATION)


# ========== Ввод имени ==========
async def get_name_input_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_name_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенного имени """
    dialog_manager.dialog_data['applicant_name'] = value
    await dialog_manager.switch_to(PropertyDatabase.CREATE_APPLICATION)


# ========== Ввод цели ==========
async def get_purpose_input_data(**_kwargs) -> dict[str, Any]:
    return {}


async def on_purpose_input(msg: Message, _widget: TextInput, dialog_manager: DialogManager, value: str):
    """ Сохранение введенной цели """
    dialog_manager.dialog_data['purpose'] = value
    await dialog_manager.switch_to(PropertyDatabase.CREATE_APPLICATION)


# ========== Выбор предметов ==========
async def get_categories_for_selection(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает список категорий для выбора предметов """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    categories = await get_all_categories(session)
    return {'categories': categories}


async def on_category_selected_for_items(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, category_id: str):
    """ Сохраняет выбранную категорию для выбора предметов """
    dialog_manager.dialog_data['selected_category_id_for_items'] = int(category_id)
    await dialog_manager.switch_to(PropertyDatabase.SELECT_ITEMS_FROM_CATEGORY)


async def get_items_for_selection(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает список предметов выбранной категории для выбора """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    category_id = dialog_manager.dialog_data.get('selected_category_id_for_items')
    
    if not category_id:
        return {'items': [], 'category_name': ''}
    
    category = await get_category_by_id(session, category_id)
    items = await get_items_by_category_id(session, category_id)
    
    return {
        'items': items,
        'category_name': category.name if category else ''
    }


async def on_item_selected(clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, item_id: str):
    """ Обработка выбора предмета - добавляем с количеством 1 """
    selected_items = dialog_manager.dialog_data.get('selected_items', {})
    selected_items[int(item_id)] = selected_items.get(int(item_id), 0) + 1
    dialog_manager.dialog_data['selected_items'] = selected_items
    await clb.answer(f"Предмет добавлен (количество: {selected_items[int(item_id)]})")


# ========== Просмотр заявки ==========
async def get_review_data(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """ Получает данные для просмотра заявки """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    applicant_name = dialog_manager.dialog_data.get('applicant_name', '')
    purpose = dialog_manager.dialog_data.get('purpose', '')
    selected_items = dialog_manager.dialog_data.get('selected_items', {})
    
    # Формируем список выбранных предметов
    items_list = []
    for item_id, quantity in selected_items.items():
        item = await get_item_by_id(session, item_id)
        if item:
            items_list.append(f"{item.name} - {quantity} {item.unit}")
    
    items_text = "\n".join(items_list) if items_list else "Нет предметов"
    
    return {
        'applicant_name': applicant_name,
        'purpose': purpose,
        'items_text': items_text
    }


async def on_confirm_application(clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """ Подтверждение и создание заявки """
    session: AsyncSession = dialog_manager.middleware_data[SESSION_KEY]
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    
    applicant_name = dialog_manager.dialog_data.get('applicant_name')
    purpose = dialog_manager.dialog_data.get('purpose')
    selected_items = dialog_manager.dialog_data.get('selected_items', {})
    
    # Получаем person_id
    person = await get_person_by_telegram_id(session, clb.from_user.id)
    if not person:
        await clb.answer("Ошибка: пользователь не найден", show_alert=True)
        return
    
    # Создаем заявку
    application = await create_application(
        session=session,
        person_id=person.id,
        applicant_name=applicant_name,
        purpose=purpose,
        items_with_quantities=selected_items
    )
    
    # Отправляем уведомление казначею
    if TelegramKeys.TREASURER_ID:
        await clb.bot.send_message(
            TelegramKeys.TREASURER_ID,
            f"Новая заявка на использование имущества:\n"
            f"Заявитель: {applicant_name}\n"
            f"Цель: {purpose}\n"
            f"ID заявки: {application.id}"
        )
    
    await dialog_manager.switch_to(PropertyDatabase.CONFIRM_APPLICATION)


# ========== Подтверждение отправки ==========
async def get_confirm_data(**_kwargs) -> dict[str, Any]:
    return {}


property_database_dialog = Dialog(
    Window(  # Главное меню
        L10nFormat('property-database-main-menu'),
        Row(
            Button(
                L10nFormat('show-list-button'),
                id='show_list',
                on_click=on_show_list_clicked
            ),
            Button(
                L10nFormat('create-application-button'),
                id='create_application',
                on_click=on_create_application_clicked
            )
        ),
        getter=get_main_menu_data,
        state=PropertyDatabase.MAIN_MENU,
    ),
    Window(  # Выбор категории для просмотра списка
        Const("Выберите категорию:"),
        ScrollingGroup(
            Select(
                Format('{item.name}'),
                id='categories_select',
                item_id_getter=lambda x: str(x.id),
                items='categories',
                on_click=on_category_selected_for_list
            ),
            id='categories_scroll',
            width=2,
            height=5,
            hide_on_single_page=True
        ),
        Back(L10nFormat('back')),
        getter=get_categories_list,
        state=PropertyDatabase.SHOW_LIST_CATEGORY,
    ),
    Window(  # Список предметов категории
        Multi(
            Format("Доступное имущество категории: {category_name}\n\n"),
            Format("{items_text}"),
            sep="\n"
        ),
        Back(L10nFormat('back')),
        getter=get_items_list,
        state=PropertyDatabase.SHOW_LIST_ITEMS,
    ),
    Window(  # Форма создания заявки
        Multi(
            Const("Для оформления заявки Вам необходимо заполнить следующие данные:\n"),
            Const("1. Ваше имя\n"),
            Const("2. Цель взятия\n"),
            Const("3. Выберите предметы и их количество\n\n"),
            Format("Имя: {applicant_name}\n"),
            Format("Цель: {purpose}\n"),
            Format("Предметы: {items_text}")
        ),
        Row(
            Button(
                Const("Имя"),
                id='input_name',
                on_click=on_name_clicked
            ),
            Button(
                Const("Цель"),
                id='input_purpose',
                on_click=on_purpose_clicked
            ),
            Button(
                Const("Предметы"),
                id='select_items',
                on_click=on_items_clicked
            )
        ),
        Row(
            Button(
                Const("Просмотр заявки"),
                id='review_application',
                on_click=on_review_clicked,
                when=F['applicant_name'] & F['purpose'] & F['selected_items']
            )
        ),
        Back(L10nFormat('back')),
        getter=get_application_form_data,
        state=PropertyDatabase.CREATE_APPLICATION,
    ),
    Window(  # Ввод имени
        Const("Введите ваше имя:"),
        TextInput('input_name', on_success=on_name_input),
        Back(L10nFormat('back')),
        getter=get_name_input_data,
        state=PropertyDatabase.INPUT_NAME,
    ),
    Window(  # Ввод цели
        Const("Введите цель взятия имущества:"),
        TextInput('input_purpose', on_success=on_purpose_input),
        Back(L10nFormat('back')),
        getter=get_purpose_input_data,
        state=PropertyDatabase.INPUT_PURPOSE,
    ),
    Window(  # Выбор категории для предметов
        Const("Выберите категорию для выбора предметов:"),
        ScrollingGroup(
            Select(
                Format('{item.name}'),
                id='categories_select_items',
                item_id_getter=lambda x: str(x.id),
                items='categories',
                on_click=on_category_selected_for_items
            ),
            id='categories_scroll_items',
            width=2,
            height=5,
            hide_on_single_page=True
        ),
        Back(L10nFormat('back')),
        getter=get_categories_for_selection,
        state=PropertyDatabase.SELECT_ITEMS,
    ),
    Window(  # Выбор предметов из категории
        Multi(
            Format("Выберите предметы из категории: {category_name}\n\n"),
            Const("Нажмите на предмет, чтобы добавить его в заявку (количество увеличивается при каждом нажатии)"),
            sep="\n"
        ),
        ScrollingGroup(
            Select(
                Format('{item.name} ({item.count} {item.unit} доступно)'),
                id='items_select',
                item_id_getter=lambda x: str(x.id),
                items='items',
                on_click=on_item_selected
            ),
            id='items_scroll',
            width=1,
            height=5,
            hide_on_single_page=True
        ),
        Row(
            Button(
                Const("Вернуться к выбору категории"),
                id='back_to_categories',
                on_click=lambda c, b, d: d.switch_to(PropertyDatabase.SELECT_ITEMS)
            )
        ),
        Back(L10nFormat('back')),
        getter=get_items_for_selection,
        state=PropertyDatabase.SELECT_ITEMS_FROM_CATEGORY,
    ),
    Window(  # Просмотр заявки
        Multi(
            Const("Подтвердите отправку заявки:\n\n"),
            Format("Имя: {applicant_name}\n"),
            Format("Цель: {purpose}\n\n"),
            Const("Выбранные предметы:\n"),
            Format("{items_text}")
        ),
        Row(
            Button(
                Const("Подтвердить отправку заявки"),
                id='confirm_application',
                on_click=on_confirm_application
            )
        ),
        Back(L10nFormat('back')),
        getter=get_review_data,
        state=PropertyDatabase.REVIEW_APPLICATION,
    ),
    Window(  # Подтверждение отправки
        Const("Ваша заявка принята, Казначей свяжется с Вами в ближайшее время"),
        Button(
            Const("В главное меню"),
            id='to_main_menu',
            on_click=lambda c, b, d: d.switch_to(PropertyDatabase.MAIN_MENU)
        ),
        getter=get_confirm_data,
        state=PropertyDatabase.CONFIRM_APPLICATION,
    ),
)

