"""Проверка ответов по JSON Schema перед созданием документа: какие схемы и ответы бота проходят."""

import pytest

from includes import load_schema, validate_data
from includes.templates import create_context
from includes.templates.contexts import ArrayContext, BaseContext

_SCHEMA = {
    "type": "object",
    "properties": {
        "number": {"type": "integer", "description": "Номер"},
        "note": {"type": "string", "description": "Примечание"},
        "tasks": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["text"],
                "properties": {"text": {"type": "string", "description": "Задача"}, "due": {"type": "string"}},
            },
        },
    },
    "required": ["number"],
}


def _answer(context: BaseContext, value: str) -> None:
    context.set_value(context.parse(value))


def test_unfilled_optional_field_passes() -> None:
    assert validate_data(_SCHEMA, {"number": 1, "note": None, "tasks": []}) == (True, None)


def test_nested_unfilled_optional_field_passes() -> None:
    data = {"number": 1, "tasks": [{"text": "Задача", "due": None}]}

    assert validate_data(_SCHEMA, data) == (True, None)


def test_missing_required_field_fails() -> None:
    success, _field = validate_data(_SCHEMA, {"number": None})

    assert success is False


def test_error_names_the_field() -> None:
    assert validate_data(_SCHEMA, {"number": "много"}) == (False, "Номер")


def test_required_field_missing_from_properties_does_not_block() -> None:
    """Такой есть в настоящем шаблоне: вопроса на это поле нет, и пользователь не смог бы создать документ."""
    schema = {**_SCHEMA, "required": ["number", "typo_in_template"]}

    assert validate_data(schema, {"number": 1}) == (True, None)


def test_declared_required_still_fails_next_to_undeclared() -> None:
    schema = {**_SCHEMA, "required": ["number", "typo_in_template"]}

    success, _field = validate_data(schema, {"note": "текст"})

    assert success is False


def test_long_field_name_fits_telegram_alert() -> None:
    schema = {"type": "object", "properties": {"n": {"type": "integer", "description": "Поле " * 100}}}

    _success, field = validate_data(schema, {"n": "много"})

    assert len(field) == 150


@pytest.mark.parametrize(
    ("resource", "answers"),
    [
        ("refunds/apply.json", {"reason": "Такси", "total_price": "1500.50", "requisites": "Телефон"}),
        (
            "equipments/apply_equipment.json",
            {"decree_date": "01.02.2026", "surname_user": "Иванов", "name_user": "Иван"},
        ),
    ],
)
def test_bot_schemas_accept_real_answers(resource: str, answers: dict[str, str]) -> None:
    """Эти схемы проверяются в заявках: исправленная проверка не должна отклонять обычные ответы."""
    schema = load_schema(resource)
    root = create_context(schema)
    for key, value in answers.items():
        _answer(root.view(key), value)

    assert validate_data(schema, root.generate_context()) == (True, None)


def test_refund_rejects_text_instead_of_sum() -> None:
    schema = load_schema("refunds/apply.json")
    root = create_context(schema)
    for key, value in {"reason": "Такси", "total_price": "много", "requisites": "Телефон"}.items():
        _answer(root.view(key), value)

    assert validate_data(schema, root.generate_context()) == (False, "Сумма")


class TestArrayOfPrimitives:
    _ARRAY = {"type": "array", "title": "Задачи", "items": {"type": "string", "description": "Задача"}}

    def test_unfilled_item_is_dropped(self) -> None:
        array = create_context(self._ARRAY)
        array.do(ArrayContext.ADD_ITEM)
        _answer(array.do(ArrayContext.ADD_ITEM), "Заказать зал")

        assert array.get_value() == ["Заказать зал"]

    def test_required_array_of_unfilled_items_is_not_filled(self) -> None:
        array = create_context(self._ARRAY, required=True)
        item = array.do(ArrayContext.ADD_ITEM)
        assert not array.filled_required()

        _answer(item, "Заказать зал")

        assert array.filled_required()
