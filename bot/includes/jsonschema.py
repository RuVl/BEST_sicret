import json

from docxtpl import DocxTemplate
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from env import ProjectKeys


def get_available_templates() -> list[str]:
	""" Return available user """

	template_names = [
		f.stem
		for f in ProjectKeys.TEMPLATES_DIR.glob('*.docx')
		if (ProjectKeys.TEMPLATES_DIR / f'{f.stem}.json').exists()
	]

	return template_names


def load_schema(template_name: str) -> dict:
	""" Load schema from JSON file """

	template_path = ProjectKeys.TEMPLATES_DIR / f'{template_name}.json'
	if not template_path.exists():
		raise FileNotFoundError(f'Schema file {template_path} not found')

	with open(template_path, 'r', encoding='utf-8') as template:
		return json.load(template)


def validate_data(schema: dict, data: dict) -> tuple[bool, str | None]:
	""" Validate user data by a schema """

	try:
		validate(schema, data)
		return True, None
	except ValidationError as e:
		return False, e.message


def generate_document(template_name: str, data: dict) -> DocxTemplate:
	""" Render the document from template with data """

	template_path = ProjectKeys.TEMPLATES_DIR / f'{template_name}.docx'
	if not template_path.exists():
		raise FileNotFoundError(f'Template file {template_path} not found')

	doc = DocxTemplate(template_path)
	doc.render(data)
	return doc
