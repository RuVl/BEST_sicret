from jsonschema import validate
from jsonschema.exceptions import ValidationError

CATEGORY_SCHEMA = {
    "type": "object",
    "properties": {"name": {"type": "string", "minLength": 2, "maxLength": 50}},
    "required": ["name"],
    "additionalProperties": False
}

EQUIPMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "category_id": {"type": "integer"},
        "name": {"type": "string", "minLength": 2, "maxLength": 100},
        "description": {"type": "string", "maxLength": 500},
        "quantity": {"type": "integer", "minimum": 1}
    },
    "required": ["category_id", "name", "quantity"],
    "additionalProperties": False
}


def validate_data(schema: dict, data: dict) -> tuple[bool, str | None]:
    try:
        validate(schema, data)
        return True, None
    except ValidationError as e:
        return False, e.message
