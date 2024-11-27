from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from fluent.runtime import FluentLocalization

from bot.includes.jsonschema import get_available_templates
from bot.keyboards.callback_factories import AskActionFactory, TemplateFactory
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


def template_properties_ikb(schema: dict,  l10n: FluentLocalization, user_data=None, *, page=0) -> InlineKeyboardMarkup:
    """ Returns inline keyboard to choose action for chosen template """

    properties: dict = schema.get("properties")
    if properties is None:
        raise ValueError(f"Properties not found for schema: {schema.get('title')}")

    properties_list = [
        {'name': k, **v}
        for k, v in properties.items()
    ]

    def property2ikb(prop: dict) -> InlineKeyboardButton:
        type_ = prop.get("type")
        description = prop.get("short_description", prop.get("description"))  # short_description or description

        if type_ is None or description is None:
            raise ValueError(f'Property "{prop['name']}" should have type and description')

        callback_data = AskActionFactory(data=prop['name'], type=type_).pack()
        return InlineKeyboardButton(
            text=description,
            callback_data=callback_data,
        )

    builder = paginate(properties_list, page, property2ikb, AskActionFactory.__prefix__)

    required = schema.get("required", [])

    if user_data is None and len(required) > 0:
        return builder.as_markup()

    # If all required fields are filled, we can generate the document
    user_data = user_data or {}

    if len(required - user_data.keys()) > 0:
        return builder.as_markup()

    return builder.row(InlineKeyboardButton(
        text=l10n.format_value('generate-document'),
        callback_data='generate_document',
    )).as_markup()
