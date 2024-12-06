import json

from docxtpl import DocxTemplate
from jsonschema import validate
from jsonschema.exceptions import ValidationError

from bot.config_reader import get_config, TemplatesConfig


def get_available_templates() -> list[str]:
    """ Return available templates """

    config: TemplatesConfig = get_config(TemplatesConfig)

    template_names = [
        f.stem
        for f in config.root.glob('*.docx')
        if (config.root / f'{f.stem}.json').exists()
    ]

    return template_names


def load_schema(template_name: str) -> dict:
    """ Load schema from JSON file """

    config: TemplatesConfig = get_config(TemplatesConfig)

    template_path = config.root / f'{template_name}.json'
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


def generate_document(template_name: str, context: dict) -> DocxTemplate:
    """ Render the document from template with context """

    config: TemplatesConfig = get_config(TemplatesConfig)

    template_path = config.root / f'{template_name}.docx'
    if not template_path.exists():
        raise FileNotFoundError(f'Template file {template_path} not found')

    doc = DocxTemplate(template_path)
    doc.render(context)
    return doc
