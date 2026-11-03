import asyncio
import time

import pytest
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError
from aiogram.methods import DeleteMessage

from includes import config_hide, pending_hides
from includes.memory_media import memory_media
from includes.pending_hides import PendingHides
from tests.fakes import FakeRedis

CHAT = 10


class FakeBot:
    """Чат глазами человека: какие сообщения в нём остались. ``fail_with`` - ошибки на ближайшие вызовы."""

    def __init__(self, messages: set[int]) -> None:
        self.chat = set(messages)
        self.fail_with: Exception | None = None
        self.fail_times: int | None = None  # None - всегда, число - столько вызовов подряд
        self.calls = 0

    async def delete_messages(self, chat_id: int, message_ids: list[int]) -> bool:
        self.calls += 1
        if self.fail_with is not None and (self.fail_times is None or self.fail_times > 0):
            if self.fail_times is not None:
                self.fail_times -= 1
            raise self.fail_with
        # Как Bot API: ненайденные сообщения deleteMessages просто пропускает.
        self.chat -= set(message_ids)
        return True


@pytest.fixture
def redis(monkeypatch) -> FakeRedis:
    fake = FakeRedis()
    monkeypatch.setattr(pending_hides, "_registry", PendingHides(fake))
    return fake


def restart(monkeypatch, redis: FakeRedis) -> None:
    """Новый процесс: память реестра пуста, Redis тот же."""
    monkeypatch.setattr(pending_hides, "_registry", PendingHides(redis))


async def show_config(token: str, messages: list[int], created_at: float | None = None) -> None:
    """Окно конфига показано, файл ушёл сообщениями ``messages`` (как их сообщил бы менеджер сообщений)."""
    await config_hide.track_config(token, user_id=1, chat_id=CHAT, stack_id="s")
    if created_at is not None:
        hide = pending_hides.get_pending_hides().get(token)
        await pending_hides.get_pending_hides().add(
            pending_hides.PendingHide(**{**hide.__dict__, "created_at": created_at})
        )
    for message_id in messages:
        await config_hide._on_media_sent(token, CHAT, message_id)


class TestHide:
    def test_every_copy_deleted_and_record_removed(self, redis):
        bot = FakeBot({100, 101, 7})

        async def scenario():
            await show_config("t", [100, 101])
            return await config_hide.hide_now(bot, "t")

        assert asyncio.run(scenario()) is True
        assert bot.chat == {7}  # чужие сообщения не тронуты
        assert asyncio.run(pending_hides.get_pending_hides().load_all()) == []

    def test_failed_delete_keeps_record_for_retry(self, redis, monkeypatch):
        bot = FakeBot({100, 101})
        bot.fail_with = TelegramNetworkError(DeleteMessage(chat_id=CHAT, message_id=0), "timeout")

        async def first():
            await show_config("t", [100, 101])
            return await config_hide.hide_now(bot, "t")

        assert asyncio.run(first()) is False
        assert bot.chat == {100, 101}

        restart(monkeypatch, redis)
        bot.fail_with = None
        asyncio.run(config_hide.hide_leftover_configs(bot))
        assert bot.chat == set()
        assert asyncio.run(pending_hides.get_pending_hides().load_all()) == []

    def test_one_request_for_all_copies(self, redis):
        bot = FakeBot({100, 101, 102})

        async def scenario():
            await show_config("t", [100, 101, 102])
            await config_hide.hide_now(bot, "t")

        asyncio.run(scenario())
        assert bot.calls == 1

    def test_cannot_be_deleted_is_final(self, redis):
        bot = FakeBot({100})
        method = DeleteMessage(chat_id=CHAT, message_id=0)
        bot.fail_with = TelegramBadRequest(method, "message can't be deleted")

        async def scenario():
            await show_config("t", [100])
            return await config_hide.hide_now(bot, "t")

        assert asyncio.run(scenario()) is True

    def test_already_deleted_is_success(self, redis):
        bot = FakeBot(set())  # человек сам удалил сообщения

        async def scenario():
            await show_config("t", [100])
            return await config_hide.hide_now(bot, "t")

        assert asyncio.run(scenario()) is True

    def test_too_old_to_delete_is_given_up(self, redis):
        bot = FakeBot({100})
        bot.fail_with = TelegramNetworkError(DeleteMessage(chat_id=CHAT, message_id=0), "timeout")

        async def scenario():
            await show_config("t", [100], created_at=time.time() - 49 * 3600)
            return await config_hide.hide_now(bot, "t")

        assert asyncio.run(scenario()) is True
        assert asyncio.run(pending_hides.get_pending_hides().load_all()) == []

    def test_bytes_dropped_even_if_delete_failed(self, redis):
        bot = FakeBot({100})
        bot.fail_with = TelegramNetworkError(DeleteMessage(chat_id=CHAT, message_id=0), "timeout")

        async def scenario():
            url = memory_media.put(b"key", "a.conf", owner="t")
            await show_config("t", [100])
            await config_hide.hide_now(bot, "t")
            return url

        url = asyncio.run(scenario())
        assert not memory_media.has(url)
        memory_media.release_owner("t")


class TestTimer:
    def test_bot_shutdown_keeps_record(self, redis, monkeypatch):
        """Остановка бота отменяет таймер - запись остаётся, и следующий старт скрывает конфиг."""
        bot = FakeBot({100})
        monkeypatch.setattr(config_hide, "_timers", {})

        async def scenario():
            await show_config("t", [100])
            config_hide.schedule_hide(bot, "t", delay=60)
            await asyncio.sleep(0)
            config_hide.cancel_timer("t")  # как asyncio.run при SIGTERM
            await asyncio.sleep(0)

        asyncio.run(scenario())
        assert bot.chat == {100}

        restart(monkeypatch, redis)
        asyncio.run(config_hide.hide_leftover_configs(bot))
        assert bot.chat == set()

    def test_timer_hides_and_refreshes(self, redis, monkeypatch):
        bot = FakeBot({100})
        refreshed = []
        monkeypatch.setattr(config_hide, "_timers", {})

        async def refresh():
            refreshed.append(True)

        async def scenario():
            await show_config("t", [100])
            config_hide.schedule_hide(bot, "t", delay=0, refresh=refresh)
            await asyncio.sleep(0.01)

        asyncio.run(scenario())
        assert bot.chat == set()
        assert refreshed == [True]

    def test_timer_retries_transient_failure(self, redis, monkeypatch):
        """Telegram временно не дал удалить - таймер повторяет, а не ждёт рестарта бота."""
        bot = FakeBot({100})
        bot.fail_with = TelegramNetworkError(DeleteMessage(chat_id=CHAT, message_id=0), "timeout")
        bot.fail_times = 2
        monkeypatch.setattr(config_hide, "_timers", {})
        monkeypatch.setattr(config_hide, "_RETRY_FIRST_SECONDS", 0.001)

        async def scenario():
            await show_config("t", [100])
            config_hide.schedule_hide(bot, "t", delay=0)
            await asyncio.sleep(0.05)

        asyncio.run(scenario())
        assert bot.chat == set()
        assert bot.calls == 3
        assert asyncio.run(pending_hides.get_pending_hides().load_all()) == []

    def test_timer_error_is_logged_not_raised(self, redis, monkeypatch):
        bot = FakeBot({100})
        monkeypatch.setattr(config_hide, "_timers", {})

        async def refresh():
            raise RuntimeError("dialog gone")

        async def scenario():
            loop = asyncio.get_running_loop()
            errors = []
            loop.set_exception_handler(lambda _loop, context: errors.append(context))
            await show_config("t", [100])
            config_hide.schedule_hide(bot, "t", delay=0, refresh=refresh)
            await asyncio.sleep(0.01)
            return errors

        assert asyncio.run(scenario()) == []
        assert bot.chat == set()


class TestTracking:
    def test_unknown_owner_ignored(self, redis):
        async def scenario():
            await config_hide._on_media_sent("not-a-config", CHAT, 5)
            return await pending_hides.get_pending_hides().messages("not-a-config")

        assert asyncio.run(scenario()) == set()
