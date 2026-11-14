"""Ответы пользователя в шаблонах: разбор ввода и попадание текста в документ без потерь."""

from io import BytesIO
from pathlib import Path

import pytest
from docx import Document

from env import settings
from includes.jsonschema import generate_document
from includes.templates import create_context

_DEMO_DIR = Path(__file__).resolve().parents[1] / "resources" / "demo_templates"


@pytest.mark.parametrize("value", ["18:00", "9:30", "23:59"])
def test_time_field_accepts_valid_time(value: str) -> None:
    field = create_context({"type": "string", "format": "time"})

    assert field.parse(value) == value


@pytest.mark.parametrize("value", ["25:00", "18.00", "вечером"])
def test_time_field_rejects_other_text(value: str) -> None:
    field = create_context({"type": "string", "format": "time"})

    with pytest.raises(ValueError, match="invalid-value"):
        field.parse(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("12500", 12500.0), ("12 500", 12500.0), ("12\xa0500,50", 12500.5), ("1 000.25", 1000.25)],
)
def test_number_field_understands_digit_groups(value: str, expected: float) -> None:
    assert create_context({"type": "number"}).parse(value) == expected


def test_special_characters_reach_document(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings.project, "TEMPLATES_DIR", _DEMO_DIR)
    event = "Турнир R&D <финал> \"2026\" и 'ещё'"
    data = {
        "order_number": 7,
        "order_date": "01.02.2026",
        "event_name": event,
        "responsible": "Иванов Иван",
        "tasks": [{"text": "Заказать зал"}],
    }

    buffer = BytesIO()
    generate_document("Демо-приказ", data).save(buffer)
    text = "\n".join(paragraph.text for paragraph in Document(BytesIO(buffer.getvalue())).paragraphs)

    assert event in text
    assert "Заказать зал" in text
