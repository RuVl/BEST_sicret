"""
Универсальный диалог для работы с формами на основе JSON схем.
Использует систему шаблонов для навигации и заполнения данных,
но вместо генерации документа вызывает кастомный callback для сохранения в БД.
"""
from typing import Any, Callable, Awaitable

from aiogram import F
from aiogram.types import CallbackQuery, Message
from aiogram_dialog import Dialog, Window, DialogManager
from aiogram_dialog.widgets.input import TextInput
from aiogram_dialog.widgets.kbd import ScrollingGroup, Select, Row, Button, Back
from aiogram_dialog.widgets.text import Format, Multi, Const
from fluent.runtime import FluentLocalization

from includes.jsonschema import load_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import BaseContext, PrimitiveContext
from middlewares import L10N_FORMAT_KEY
from state_machines.form_by_schema import FormBySchema
from utils import L10nFormat


async def get_form_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """Получает данные для отображения формы"""
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context: BaseContext = dialog_manager.dialog_data.get('context')
    form_title: str = dialog_manager.dialog_data.get('form_title', 'Форма')
    form_description: str = dialog_manager.dialog_data.get('form_description', '')
    
    return {
        'form_title': form_title,
        'form_description': form_description,
        'view': context.render_view(l10n),
        'data_kb': context.render_data_kb(l10n),
        'action_kb': context.render_action_kb(l10n),
        'can_submit': context.can_generate(),
    }


async def on_data_selected(_clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, data: str):
    """Обработка выбора поля для редактирования"""
    context: BaseContext = dialog_manager.dialog_data.get('context')
    context = context.view(data)

    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(FormBySchema.ADD if isinstance(context, PrimitiveContext) else FormBySchema.VIEW)


async def on_action_selected(_clb: CallbackQuery, _select: Select, dialog_manager: DialogManager, action: str):
    """Обработка действий (назад, удалить, добавить элемент)"""
    context: BaseContext = dialog_manager.dialog_data.get('context')
    context = context.do(action)

    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(FormBySchema.VIEW)


async def on_submit_form(clb: CallbackQuery, _button: Button, dialog_manager: DialogManager):
    """Обработка отправки формы - вызывает кастомный callback"""
    context: BaseContext = dialog_manager.dialog_data.get('context')
    schema_name: str = dialog_manager.dialog_data.get('schema_name')
    
    # Генерируем данные из контекста
    data = context.generate_context()
    
    # Валидируем данные
    schema = load_schema(schema_name)
    success, error_msg = validate_data(schema, data)
    if not success:
        await clb.answer(error_msg, show_alert=True)
        return
    
    # Получаем кастомный callback для сохранения
    save_callback: Callable[[CallbackQuery, DialogManager, dict], Awaitable[None]] = dialog_manager.dialog_data.get('save_callback')
    
    if save_callback:
        await save_callback(clb, dialog_manager, data)
    else:
        await clb.answer("Ошибка: callback для сохранения не определен", show_alert=True)


async def get_property_context(dialog_manager: DialogManager, **_kwargs) -> dict[str, Any]:
    """Получает данные для окна редактирования поля"""
    l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
    context: PrimitiveContext = dialog_manager.dialog_data.get('context')
    return {
        'question': context.ask_question(),
        'action_kb': context.render_action_kb(l10n),
        'can_submit': context.can_generate(),
    }


async def set_property(msg: Message, _: TextInput, dialog_manager: DialogManager, value: str):
    """Сохранение значения поля"""
    context: PrimitiveContext = dialog_manager.dialog_data.get('context')
    try:
        parsed_value = context.parse(value)
    except ValueError as e:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        await msg.answer(l10n.format_value(str(e)))
        return

    context.set_value(parsed_value)
    try:  # try to go back
        context = context.do('back')
    except ValueError:
        await dialog_manager.switch_to(FormBySchema.VIEW)
        return

    dialog_manager.dialog_data.update(context=context)
    await dialog_manager.switch_to(FormBySchema.VIEW)


async def start_form_dialog(
    dialog_manager: DialogManager,
    schema_name: str,
    form_title: str,
    form_description: str,
    save_callback: Callable[[CallbackQuery, DialogManager, dict], Awaitable[None]],
    initial_state=FormBySchema.VIEW
):
    """
    Инициализирует и запускает диалог формы.
    
    Args:
        dialog_manager: DialogManager для запуска диалога
        schema_name: Имя схемы (без расширения .json)
        form_title: Заголовок формы
        form_description: Описание формы
        save_callback: Callback функция для сохранения данных (clb, dialog_manager, data)
        initial_state: Начальное состояние диалога
    """
    from aiogram_dialog import StartMode, ShowMode
    
    try:
        schema = load_schema(schema_name)
        context = create_context(schema)
    except FileNotFoundError:
        l10n: FluentLocalization = dialog_manager.middleware_data.get(L10N_FORMAT_KEY)
        # Ошибка будет обработана в on_schema_selected
        return
    
    # Инициализируем данные диалога
    dialog_manager.dialog_data.update(
        schema_name=schema_name,
        form_title=form_title,
        form_description=form_description,
        context=context,
        save_callback=save_callback
    )
    
    # Определяем начальное состояние
    start_state = FormBySchema.ADD if isinstance(context, PrimitiveContext) else FormBySchema.VIEW
    
    # Переходим к форме
    await dialog_manager.start(
        start_state,
        mode=StartMode.RESET_STACK,
        show_mode=ShowMode.DELETE_AND_SEND
    )


# Универсальный диалог для работы с формами на основе JSON схем
form_by_schema_dialog = Dialog(
        Window(  # Окно просмотра формы
            Multi(
                Format('*{form_title}*\n_{form_description}_\n\n'),
                Format('{view}\n\n'),
                Const(r'_\* \- '),
                L10nFormat('required-hint'),
                Const('_'),
                sep=''
            ),
            ScrollingGroup(
                Select(
                    Format('{item[0]}'),
                    id='form_change',
                    item_id_getter=lambda x: x[1],
                    items='data_kb',
                    on_click=on_data_selected
                ),
                id='form_scroll',
                width=2,
                height=5,
                hide_on_single_page=True
            ),
            Select(
                Format('{item[0]}'),
                id='form_action',
                item_id_getter=lambda x: x[1],
                items='action_kb',
                on_click=on_action_selected
            ),
            Row(Button(
                L10nFormat('submit-application'),
                id='submit_form',
                on_click=on_submit_form,
                when=F['can_submit']
            )),
            getter=get_form_context,
            state=FormBySchema.VIEW,
        ),
        Window(  # Окно редактирования поля
            Format('{question}'),
            TextInput('input_property', on_success=set_property),
            Select(
                Format('{item[0]}'),
                id='form_action',
                item_id_getter=lambda x: x[1],
                items='action_kb',
                on_click=on_action_selected
            ),
            getter=get_property_context,
            state=FormBySchema.ADD,
        )
)

