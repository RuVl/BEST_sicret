"""Медиа из памяти процесса для окон aiogram-dialog.

aiogram-dialog отправляет медиа окна только по ``file_id``, пути на диске или URL. Конфиг
AmneziaWG - приватный ключ: на диск ему нельзя, а получить ``file_id`` можно лишь отправив
файл отдельным сообщением (оно мелькает в чате). Поэтому файл кладётся сюда, окно ссылается
на него URL'ом ``memory://<id>``, а ``MemoryMediaMessageManager`` подставляет вместо URL сами
байты. Файл уходит в Telegram сразу как сообщение окна; дальше aiogram-dialog сам запоминает
его ``file_id`` (``MediaIdStorage``) и при перерисовке байты больше не нужны.

Хранилище живёт в памяти процесса: после рестарта бота ссылки протухают - вызывающая сторона
проверяет ``has`` и показывает окно без медиа.
"""

from uuid import uuid4

from aiogram import Bot
from aiogram.types import BufferedInputFile, InputFile
from aiogram_dialog.api.entities import MediaAttachment
from aiogram_dialog.manager.message_manager import MessageManager

SCHEME = "memory://"


class MemoryMediaStore:
    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, str]] = {}

    def put(self, data: bytes, filename: str) -> str:
        """Положить файл и вернуть URL для ``MediaAttachment(url=...)``."""
        url = f"{SCHEME}{uuid4().hex}"
        self._files[url] = (data, filename)
        return url

    def has(self, url: str | None) -> bool:
        return url in self._files

    def get(self, url: str) -> BufferedInputFile | None:
        stored = self._files.get(url)
        if stored is None:
            return None
        data, filename = stored
        return BufferedInputFile(data, filename=filename)

    def drop(self, *urls: str | None) -> None:
        for url in urls:
            self._files.pop(url, None)


memory_media = MemoryMediaStore()


class MemoryMediaMessageManager(MessageManager):
    """``MessageManager``, который умеет отдавать в Telegram файлы из ``memory_media``."""

    async def get_media_source(self, media: MediaAttachment, bot: Bot) -> InputFile | str:
        # Если file_id уже известен (aiogram-dialog подставил его из кэша), байты не нужны.
        if media.url and media.url.startswith(SCHEME) and not media.file_id:
            file = memory_media.get(media.url)
            if file is None:
                raise ValueError(f"Файл {media.url} уже удалён из памяти")
            return file
        return await super().get_media_source(media, bot)
