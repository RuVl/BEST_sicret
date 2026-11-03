"""Двойной клик: второй апдейт человека должен видеть результат первого (см. ``run.create_dispatcher``)."""

import asyncio
import pickle

from aiogram import Dispatcher
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.base import BaseStorage
from aiogram_dialog import Dialog, DialogManager, StartMode, Window, setup_dialogs
from aiogram_dialog.test_tools import BotClient, MockMessageManager
from aiogram_dialog.test_tools.keyboard import InlineButtonTextLocator
from aiogram_dialog.widgets.kbd import Button
from aiogram_dialog.widgets.text import Const, Format

from run import create_dispatcher


class PickleStorage(BaseStorage):
    """Как Redis: каждое чтение - независимая копия данных."""

    def __init__(self) -> None:
        self.data: dict = {}
        self.state: dict = {}

    async def set_state(self, key, state=None):
        self.state[key] = getattr(state, "state", state)

    async def get_state(self, key):
        return self.state.get(key)

    async def set_data(self, key, data):
        self.data[key] = pickle.dumps(data)

    async def get_data(self, key):
        raw = self.data.get(key)
        return pickle.loads(raw) if raw else {}

    async def close(self):
        pass


class SG(StatesGroup):
    MAIN = State()


async def on_click(callback, button, manager: DialogManager) -> None:
    count = manager.dialog_data.get("count", 0)
    await asyncio.sleep(0.05)  # запрос к панели или БД
    manager.dialog_data["count"] = count + 1


async def getter(dialog_manager: DialogManager, **kwargs):
    return {"count": dialog_manager.dialog_data.get("count", 0)}


async def start(message, dialog_manager: DialogManager) -> None:
    await dialog_manager.start(SG.MAIN, mode=StartMode.RESET_STACK)


def double_click(dp: Dispatcher) -> str:
    dp.include_router(
        Dialog(
            Window(
                Format("count={count}"), Button(Const("+1"), id="inc", on_click=on_click), getter=getter, state=SG.MAIN
            )
        )
    )
    dp.message.register(start)
    messages = MockMessageManager()
    setup_dialogs(dp, message_manager=messages)

    async def scenario() -> str:
        client = BotClient(dp)
        await client.send("/start")
        window = messages.last_message()
        await asyncio.gather(
            client.click(window, InlineButtonTextLocator(r"\+1")),
            client.click(window, InlineButtonTextLocator(r"\+1")),
        )
        return messages.last_message().text

    return asyncio.run(scenario())


def test_bot_dispatcher_serializes_user_updates():
    assert double_click(create_dispatcher(PickleStorage())) == "count=2"


def test_without_isolation_update_is_lost():
    # Контроль: тот же сценарий на Dispatcher по умолчанию теряет первый клик - тест выше проверяет именно изоляцию.
    assert double_click(Dispatcher(storage=PickleStorage())) == "count=1"
