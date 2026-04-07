import json

from jsonschema import validate
from jsonschema.exceptions import ValidationError
from env import ProjectKeys


def validate_data(schema: dict, data: dict) -> tuple[bool, str | None]:
    try:
        validate(schema, data)
        return True, None
    except ValidationError as e:
        return False, e.message


def load_schema(apply_equipment_name: str) -> dict:
    equipment_path = ProjectKeys.TEMPLATES_DIR / f'{apply_equipment_name}.json'
    if not apply_equipment_name.exists():
        raise FileNotFoundError(f'Schema file {apply_equipment_name} not found')

    with open(apply_equipment_name, 'r', encoding='utf-8') as equipment:
        return json.load(equipment)
