"""Медиа из памяти процесса для окон aiogram-dialog.

aiogram-dialog отправляет медиа окна только по ``file_id``, пути на диске или URL. Конфиг
AmneziaWG - приватный ключ: на диск ему нельзя, а получить ``file_id`` можно лишь отправив
файл отдельным сообщением (оно мелькает в чате). Поэтому файл кладётся сюда, окно ссылается
на него URL'ом ``memory://<id>``, а ``MemoryMediaMessageManager`` подставляет вместо URL сами
байты. Файл уходит в Telegram сразу как сообщение окна; дальше aiogram-dialog сам запоминает
его ``file_id`` (``MediaIdStorage``) и при перерисовке байты больше не нужны.

У файла может быть владелец (строка, например токен окна конфига). Каждое сообщение, которое
бот отправил или отредактировал с таким медиа, сообщается подписчику: aiogram-dialog помнит
только последнее сообщение окна, а копия файла могла уйти и в другие (повторная отправка окна
после реплики человека, двойной клик). Что делать с этими сообщениями, решает подписчик -
менеджер сообщений о скрытии конфигов ничего не знает.

Хранилище живёт в памяти процесса: после рестарта бота ссылки протухают - вызывающая сторона
проверяет ``has`` и показывает окно без медиа.
"""

from collections.abc import Awaitable, Callable
from uuid import uuid4

import structlog
from aiogram import Bot
from aiogram.types import BufferedInputFile, InputFile, Message
from aiogram_dialog.api.entities import MediaAttachment, NewMessage, OldMessage
from aiogram_dialog.manager.message_manager import MessageManager
from structlog.typing import FilteringBoundLogger

SCHEME = "memory://"

logger: FilteringBoundLogger = structlog.get_logger("memory-media")

# (владелец, chat_id, message_id): сообщение с медиа владельца ушло в чат.
SentListener = Callable[[str, int, int], Awaitable[None]]


class MemoryMediaStore:
    def __init__(self) -> None:
        self._files: dict[str, tuple[bytes, str]] = {}
        # Владелец переживает байты: окно с уже известным file_id может отправиться и после drop.
        self._owners: dict[str, str] = {}
        self._listener: SentListener | None = None

    def put(self, data: bytes, filename: str, owner: str | None = None) -> str:
        """Положить файл и вернуть URL для ``MediaAttachment(url=...)``."""
        url = f"{SCHEME}{uuid4().hex}"
        self._files[url] = (data, filename)
        if owner is not None:
            self._owners[url] = owner
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
        """Забыть байты. Владелец остаётся до ``release_owner``."""
        for url in urls:
            self._files.pop(url, None)

    def owner_of(self, url: str | None) -> str | None:
        return self._owners.get(url) if url else None

    def drop_owned(self, owner: str) -> None:
        """Забыть байты всех файлов владельца, оставив привязку: копии по file_id ещё учитываются."""
        self.drop(*(url for url, current in self._owners.items() if current == owner))

    def release_owner(self, owner: str) -> None:
        """Забыть все файлы владельца вместе с привязкой к нему."""
        urls = [url for url, current in self._owners.items() if current == owner]
        for url in urls:
            del self._owners[url]
        self.drop(*urls)

    def set_sent_listener(self, listener: SentListener | None) -> None:
        self._listener = listener

    async def notify_sent(self, url: str | None, message: Message) -> None:
        owner = self.owner_of(url)
        if owner is None or self._listener is None:
            return
        await self._listener(owner, message.chat.id, message.message_id)


memory_media = MemoryMediaStore()


class MemoryMediaMessageManager(MessageManager):
    """``MessageManager``, который умеет отдавать в Telegram файлы из ``memory_media``.

    Все исходящие сообщения окон проходят через ``send_message`` и ``edit_message`` (в том числе
    повторная отправка после неудачной правки), поэтому здесь видно каждую копию медиа владельца.
    """

    async def get_media_source(self, media: MediaAttachment, bot: Bot) -> InputFile | str:
        # Если file_id уже известен (aiogram-dialog подставил его из кэша), байты не нужны.
        if media.url and media.url.startswith(SCHEME) and not media.file_id:
            file = memory_media.get(media.url)
            if file is None:
                raise ValueError(f"Файл {media.url} уже удалён из памяти")
            return file
        return await super().get_media_source(media, bot)

    async def send_message(self, bot: Bot, new_message: NewMessage) -> Message:
        message = await super().send_message(bot, new_message)
        await _report(new_message, message)
        return message

    async def edit_message(self, bot: Bot, new_message: NewMessage, old_message: OldMessage) -> Message:
        message = await super().edit_message(bot, new_message, old_message)
        await _report(new_message, message)
        return message


async def _report(new_message: NewMessage, message: Message) -> None:
    if new_message.media is None:
        return
    try:
        await memory_media.notify_sent(new_message.media.url, message)
    except Exception as exc:
        # Окно уже показано: сбой учёта не должен ронять показ - но его надо видеть в логе.
        await logger.aerror("memory-media-sent-listener-failed", error=str(exc))
