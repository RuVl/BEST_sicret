"""Демо-шаблон приказа: новичок пройдёт его первым, поэтому проверяем весь путь от схемы до ``.docx``."""

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document
from docxtpl import DocxTemplate

from env import settings
from includes.jsonschema import generate_document, get_available_templates, load_template_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import ArrayContext, BaseContext

_NAME = "Демо-приказ"
_DEMO_DIR = Path(__file__).resolve().parents[1] / "resources" / "demo_templates"


@pytest.fixture(autouse=True)
def demo_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.project, "TEMPLATES_DIR", _DEMO_DIR)


def _answer(context: BaseContext, value: str) -> BaseContext:
    """Как окно ввода: разобрать ответ, сохранить значение и вернуться к родителю."""
    context.set_value(context.parse(value))
    return context.do(context.BACK_ACTION)


def test_listed_as_available() -> None:
    assert _NAME in get_available_templates()


def test_docx_uses_only_schema_fields() -> None:
    variables = DocxTemplate(_DEMO_DIR / f"{_NAME}.docx").get_undeclared_template_variables()

    assert variables == set(load_template_schema(_NAME)["properties"])


def test_answers_produce_document() -> None:
    schema = load_template_schema(_NAME)
    root = create_context(schema)
    for key, value in {
        "order_number": "7",
        "order_date": "01.02.2026",
        "event_name": "Выдуманный турнир",
        "responsible": "Иванов Иван",
    }.items():
        _answer(root.view(key), value)
    tasks = root.view("tasks")
    for task in ("Собрать команду", "Заказать зал"):
        _answer(tasks.do(ArrayContext.ADD_ITEM).view("text"), task)

    assert root.can_generate()
    data = root.generate_context()
    assert validate_data(schema, data) == (True, None)

    buffer = BytesIO()
    generate_document(_NAME, data).save(buffer)
    text = "\n".join(paragraph.text for paragraph in Document(BytesIO(buffer.getvalue())).paragraphs)

    for expected in ("ПРИКАЗ № 7", "01.02.2026", "Выдуманный турнир", "Иванов Иван"):
        assert expected in text
    assert "1. Собрать команду" in text
    assert "2. Заказать зал" in text
    assert "{{" not in text
    assert "{%" not in text


@pytest.mark.parametrize("bad_date", ["2026-02-01", "завтра"])
def test_date_format_is_checked(bad_date: str) -> None:
    root = create_context(load_template_schema(_NAME))

    with pytest.raises(ValueError):
        root.view("order_date").parse(bad_date)
