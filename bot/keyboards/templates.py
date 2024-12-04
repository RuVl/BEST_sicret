from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from bot.includes.jsonschema import get_available_templates
from bot.keyboards.callback_factories import TemplateFactory
from bot.keyboards.common import paginate


def choose_template_ikb(*, page=0, templates: list[str] = None) -> InlineKeyboardMarkup:
    """ Returns inline keyboard to choose templates """

    if templates is None:
        templates = get_available_templates()

    def template2ikb(template: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            text=template,
            callback_data=TemplateFactory(name=template).pack(),
        )

    builder = paginate(templates, page, template2ikb, TemplateFactory.__prefix__)
    return builder.as_markup()
