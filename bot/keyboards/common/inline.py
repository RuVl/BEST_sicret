import math
from typing import Callable

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from fluent.runtime import FluentLocalization

from bot.keyboards.callback_factories import PaginatorFactory


def cancel_ikb(l10n: FluentLocalization) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text=l10n.format_value('cancel-button'), callback_data='cancel'))
    return builder.as_markup()


def paginate[T](data: list[T],
                page: int,
                element2button: Callable[[T], InlineKeyboardButton],
                prefix: str, /,
                cols=2, rows=5) -> InlineKeyboardBuilder:
    """
        Create pages by inline buttons from data.
        :param data: List of data to split by page.
        :param page: Current page.
        :param element2button: Adapter data to InlineKeyboardButton.
        :param prefix: Prefix for a unique menu's change page buttons
        :param cols: Max number of columns.
        :param rows: Max number of rows.
        :return: InlineKeyboardBuilder.
    """

    if len(data) == 0:
        return InlineKeyboardBuilder()

    on_page = cols * rows  # Buttons on one page

    page_data = data[page * on_page:(page + 1) * on_page]
    max_pages = math.ceil(len(data) / on_page)

    builder = InlineKeyboardBuilder()

    for d in page_data:
        builder.add(element2button(d))

    builder.adjust(cols)

    # If there is one page
    if max_pages == 1:
        return builder

    page_switch_buttons = []

    # If it's not first page
    if page > 0:
        page_switch_buttons.append(
            InlineKeyboardButton(
                text='<',
                callback_data=PaginatorFactory(menu=prefix, action='change_page', page=page - 1).pack()
            )
        )

    page_switch_buttons.append(
        # nothing - auto ignores by middleware
        InlineKeyboardButton(text=f'·{page + 1}/{max_pages}·', callback_data='nothing')
    )

    # If it's not last page
    if page + 1 < max_pages:
        page_switch_buttons.append(
            InlineKeyboardButton(
                text='>',
                callback_data=PaginatorFactory(menu=prefix, action='change_page', page=page + 1).pack()
            )
        )

    return builder.row(*page_switch_buttons)
