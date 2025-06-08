from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from includes.jsonschema import get_available_templates
from keyboards.callback_factories import TemplateFactory
from keyboards.common import paginate


def choose_template_ikb(*, page=0, templates: list[str] = None) -> InlineKeyboardMarkup:
	""" Returns inline keyboard to choose user """

	if templates is None:
		templates = get_available_templates()

	def template2ikb(template: str) -> InlineKeyboardButton:
		return InlineKeyboardButton(
			text=template,
			callback_data=TemplateFactory(name=template).pack(),
		)

	builder = paginate(templates, page, template2ikb, TemplateFactory.__prefix__)

	# Add a special link
	builder.row(InlineKeyboardButton(
		text='Шаблоны на заполнение с/з',
		url='https://drive.google.com/drive/u/1/folders/1XPR8fKQAHT0X_4CB7i8uWCQCTT4gnWuo'
	))

	return builder.as_markup()
