import asyncio
from datetime import datetime
from types import SimpleNamespace

from aiogram.types import BufferedInputFile, Chat, ContentType, Message
from aiogram_dialog.api.entities import MediaAttachment, MediaId
from aiogram_dialog.manager.message_manager import MessageManager

from includes.memory_media import MemoryMediaMessageManager, MemoryMediaStore, memory_media


class TestMemoryMediaStore:
    def test_put_get_drop(self):
        store = MemoryMediaStore()
        url = store.put(b"secret", "a.conf")

        assert url.startswith("memory://")
        assert store.has(url)
        file = store.get(url)
        assert isinstance(file, BufferedInputFile)
        assert file.filename == "a.conf"

        store.drop(url, None)
        assert not store.has(url)
        assert store.get(url) is None

    def test_urls_are_unique(self):
        store = MemoryMediaStore()
        assert store.put(b"x", "a") != store.put(b"x", "a")


class TestMemoryMediaMessageManager:
    def _source(self, media: MediaAttachment):
        return asyncio.run(MemoryMediaMessageManager().get_media_source(media, bot=None))

    def test_memory_url_becomes_bytes(self):
        url = memory_media.put(b"[Interface]", "BEST-AWG-1.conf")
        try:
            source = self._source(MediaAttachment(ContentType.DOCUMENT, url=url))
        finally:
            memory_media.drop(url)

        assert isinstance(source, BufferedInputFile)
        assert source.filename == "BEST-AWG-1.conf"

    def test_cached_file_id_wins(self):
        # После первой отправки aiogram-dialog подставляет file_id - байты больше не нужны.
        media = MediaAttachment(ContentType.DOCUMENT, url="memory://gone", file_id=MediaId("FILE"))
        assert self._source(media) == "FILE"

    def test_ordinary_url_untouched(self):
        assert self._source(MediaAttachment(ContentType.PHOTO, url="https://example.org/a.png")) == (
            "https://example.org/a.png"
        )


class TestOwnerTracking:
    def test_owner_outlives_bytes_until_released(self):
        store = MemoryMediaStore()
        url = store.put(b"key", "a.conf", owner="tok")

        store.drop(url)
        assert store.owner_of(url) == "tok"  # file_id из кэша ещё может уйти в чат

        store.release_owner("tok")
        assert store.owner_of(url) is None

    def test_every_sent_copy_is_reported(self):
        """Повторная отправка окна (новое сообщение) и правка - обе копии видны подписчику."""
        url = memory_media.put(b"[Interface]", "BEST-AWG-1.conf", owner="tok")
        seen: list[tuple[str, int, int]] = []

        async def listener(owner: str, chat_id: int, message_id: int) -> None:
            seen.append((owner, chat_id, message_id))

        manager = _RecordingManager()
        new_message = _new_message(MediaAttachment(ContentType.DOCUMENT, url=url))
        memory_media.set_sent_listener(listener)
        try:
            asyncio.run(manager.send_message(None, new_message))
            asyncio.run(manager.edit_message(None, new_message, None))
        finally:
            memory_media.set_sent_listener(None)
            memory_media.release_owner("tok")

        assert seen == [("tok", 10, 1), ("tok", 10, 2)]

    def test_listener_failure_does_not_break_show(self):
        url = memory_media.put(b"[Interface]", "a.conf", owner="tok")

        async def listener(owner: str, chat_id: int, message_id: int) -> None:
            raise RuntimeError("boom")

        memory_media.set_sent_listener(listener)
        try:
            message = asyncio.run(
                _RecordingManager().send_message(None, _new_message(MediaAttachment(ContentType.DOCUMENT, url=url)))
            )
        finally:
            memory_media.set_sent_listener(None)
            memory_media.release_owner("tok")

        assert message.message_id == 1

    def test_text_messages_and_foreign_media_ignored(self):
        seen = []

        async def listener(*args) -> None:
            seen.append(args)

        memory_media.set_sent_listener(listener)
        try:
            manager = _RecordingManager()
            asyncio.run(manager.send_message(None, _new_message(None)))
            asyncio.run(
                manager.send_message(None, _new_message(MediaAttachment(ContentType.PHOTO, url="https://x/a.png")))
            )
        finally:
            memory_media.set_sent_listener(None)

        assert seen == []


def _new_message(media: MediaAttachment | None):
    return SimpleNamespace(media=media, chat=Chat(id=10, type="private"))


class _FakeTelegramManager(MessageManager):
    """Отправка без Telegram: каждое сообщение получает следующий id."""

    _next_id = 0

    def _message(self) -> Message:
        self._next_id += 1
        return Message(message_id=self._next_id, date=datetime.now(), chat=Chat(id=10, type="private"))

    async def send_message(self, bot, new_message):
        return self._message()

    async def edit_message(self, bot, new_message, old_message):
        return self._message()


class _RecordingManager(MemoryMediaMessageManager, _FakeTelegramManager):
    """По MRO ``super()`` обёртки учёта попадает в фейковую отправку - проверяем саму обёртку."""
