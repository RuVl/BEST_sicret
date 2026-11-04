import json
from pathlib import Path

import structlog
from docxtpl import DocxTemplate
from jsonschema.exceptions import ValidationError, best_match
from jsonschema.validators import validator_for
from structlog.typing import FilteringBoundLogger

from env import settings

logger: FilteringBoundLogger = structlog.get_logger("jsonschema")

# Telegram ограничивает текст алерта 200 символами, часть из них занимает сама фраза.
_FIELD_TRUNCATE_LEN = 150


def get_available_templates() -> list[str]:
    """Return available user"""

    template_names = [
        f.stem
        for f in settings.project.TEMPLATES_DIR.glob("*.docx")
        if (settings.project.TEMPLATES_DIR / f"{f.stem}.json").exists()
    ]

    return template_names


def load_template_schema(template_name: str) -> dict:
    """Load schema from JSON file"""

    template_path = settings.project.TEMPLATES_DIR / f"{template_name}.json"
    if not template_path.exists():
        raise FileNotFoundError(f"Schema file {template_path} not found")

    with open(template_path, encoding="utf-8") as template:
        return json.load(template)


def load_schema(resource_path: Path | str) -> dict:
    """Load schema from JSON file"""

    schema_path = Path(resource_path)

    if not schema_path.is_relative_to(settings.project.RESOURCE_DIR):
        schema_path = settings.project.RESOURCE_DIR / schema_path

    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file {schema_path} not found")

    with open(schema_path, encoding="utf-8") as schema:
        return json.load(schema)


def _without_empty(value: object) -> object:
    """Без незаполненных полей: контекст отдаёт их как ``None``, а для схемы это неверный тип, а не пропуск."""
    if isinstance(value, dict):
        return {key: _without_empty(item) for key, item in value.items() if item is not None}
    if isinstance(value, list):
        return [_without_empty(item) for item in value]
    return value


def _is_unanswerable(error: ValidationError) -> bool:
    """``required`` на поле, которого нет в ``properties``: бот его не спросит, и документ не создался бы никогда."""
    if error.validator != "required":
        return False
    declared = error.schema.get("properties", {})
    return not any(name in declared and name not in error.instance for name in error.validator_value)


def validate_data(schema: dict, data: dict) -> tuple[bool, str | None]:
    """Проверить ответы по схеме. При ошибке вторым значением идёт подпись поля для сообщения пользователю."""

    errors = []
    for error in validator_for(schema)(schema).iter_errors(_without_empty(data)):
        if _is_unanswerable(error):
            logger.warning("schema-required-not-declared", title=schema.get("title"), message=error.message)
        else:
            errors.append(error)
    if not errors:
        return True, None

    error = best_match(errors)
    field = error.schema.get("description") or error.schema.get("title") or error.json_path
    return False, field[:_FIELD_TRUNCATE_LEN]


def generate_document(template_name: str, data: dict) -> DocxTemplate:
    """Render the document from template with data"""

    template_path = settings.project.TEMPLATES_DIR / f"{template_name}.docx"
    if not template_path.exists():
        raise FileNotFoundError(f"Template file {template_path} not found")

    doc = DocxTemplate(template_path)
    # Без экранирования `&` и `<` из ответа ломают XML документа, и часть текста молча пропадает.
    doc.render(data, autoescape=True)
    return doc
