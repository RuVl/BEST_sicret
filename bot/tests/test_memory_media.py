import asyncio

from aiogram.types import BufferedInputFile, ContentType
from aiogram_dialog.api.entities import MediaAttachment, MediaId

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
