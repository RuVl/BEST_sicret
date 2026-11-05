"""Решения диалогов без Telegram: куда ведёт добавление элемента и что показать при пустом имуществе."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace

import pytest

from dialogs.user import inventory, templates
from includes.templates import create_context
from includes.templates.contexts import ArrayContext
from state_machines import CreateByTemplate
from tests.fakes import FakeL10n


class FakeManager:
    def __init__(self, dialog_data: dict) -> None:
        self.dialog_data = dialog_data
        self.start_data = None
        self.state = None

    async def switch_to(self, state, show_mode=None) -> None:
        self.state = state


@pytest.mark.parametrize(
    ("items", "state"),
    [
        ({"type": "string", "description": "Задача"}, CreateByTemplate.ADD),
        ({"type": "object", "properties": {"text": {"type": "string"}}}, CreateByTemplate.VIEW),
    ],
    ids=["primitive-asks-for-input", "object-shows-fields"],
)
def test_new_array_item_opens_right_window(items: dict, state) -> None:
    array = create_context({"type": "array", "title": "Задачи", "items": items})
    manager = FakeManager({"context": array})

    asyncio.run(templates.on_action_selected(None, None, manager, ArrayContext.ADD_ITEM))

    assert manager.state == state
    assert manager.dialog_data["context"] is not array


@pytest.mark.parametrize(
    ("categories", "key"),
    [([], "inventory-empty"), ([SimpleNamespace(id=1, name="Техника")], "choose-category")],
    ids=["empty", "with-categories"],
)
def test_categories_text(monkeypatch: pytest.MonkeyPatch, categories: list, key: str) -> None:
    @asynccontextmanager
    async def no_session():
        yield None

    async def get_categories(session):
        return categories

    monkeypatch.setattr(inventory, "async_session", no_session)
    monkeypatch.setattr(inventory, "get_categories", get_categories)

    data = asyncio.run(inventory.get_categories_data(FakeManager({}), FakeL10n()))

    assert data["text"].startswith(key)
