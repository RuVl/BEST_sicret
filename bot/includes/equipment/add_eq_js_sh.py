import json

from jsonschema import validate
from jsonschema.exceptions import ValidationError
from env import ProjectKeys


def validate_data(schema: dict, data: dict) -> tuple[bool, str | None]:

    try:
      
        validate(instance=data, schema=schema)
        return True, None
    except ValidationError as e:
        return False, e.message


def load_schema(apply_equipment_name: str) -> dict:
    equipment_path = ProjectKeys.EQUIPMENT_PERSON_DATA_DIR / f'{apply_equipment_name}.json'
    if not equipment_path.exists():
        raise FileNotFoundError(f'Schema file {equipment_path} not found')

    with open(equipment_path, 'r', encoding='utf-8') as equipment:
        return json.load(equipment)