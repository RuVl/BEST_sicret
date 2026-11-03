"""Реестр конфигов AmneziaWG, которые ещё надо убрать из чата, - со всеми их сообщениями.

Конфиг - приватный ключ. Его показывает окно диалога, но копия файла может оказаться и в других
сообщениях (aiogram-dialog пересылает окно заново после реплики человека и т.п.), поэтому реестр
помнит каждое сообщение, в которое ушёл файл (см. ``includes.memory_media``), а скрытие удаляет
их все напрямую.

Таймер живёт в памяти процесса: после рестарта (деплой, падение) сообщения с ключом остались бы
в чате, а через 48 часов Telegram их уже не даст удалить. Поэтому записи дублируются в Redis, и
при старте бот добирает всё, что не успел. Память процесса - основное состояние: если Redis
недоступен, конфиг всё равно скроется по таймеру, теряется только страховка от рестарта.
Без Redis (``USE_REDIS=False``) работает одна память.

Запись снимается только после подтверждённого скрытия (см. ``includes.config_hide``).
"""

import json
from dataclasses import asdict, dataclass

import structlog
from redis.asyncio import Redis
from redis.exceptions import RedisError
from structlog.typing import FilteringBoundLogger

from env import settings

logger: FilteringBoundLogger = structlog.get_logger("pending-hides")

_KEY = "awg:pending-hides"
_MESSAGES_KEY = "awg:pending-hides:messages:{token}"


@dataclass(frozen=True)
class PendingHide:
    """Конфиг, который ещё надо скрыть: где он показан и в каком стеке диалога его окно."""

    token: str
    user_id: int
    chat_id: int
    stack_id: str
    # Unix-время показа: сообщения старше 48 часов Telegram удалить уже не даст - такие записи не держим.
    created_at: float = 0.0


class PendingHides:
    def __init__(self, redis: Redis | None) -> None:
        self._redis = redis
        self._hides: dict[str, PendingHide] = {}
        self._messages: dict[str, set[int]] = {}

    async def add(self, hide: PendingHide) -> None:
        self._hides[hide.token] = hide
        self._messages.setdefault(hide.token, set())
        if self._redis is None:
            return
        try:
            await self._redis.hset(_KEY, hide.token, json.dumps(asdict(hide)))
        except RedisError as exc:
            await logger.awarning("pending-hide-add-failed", error=str(exc))

    async def add_message(self, token: str, message_id: int) -> None:
        """Сообщение с файлом конфига ``token`` ушло в чат."""
        self._messages.setdefault(token, set()).add(message_id)
        if self._redis is None:
            return
        try:
            await self._redis.sadd(_MESSAGES_KEY.format(token=token), message_id)
        except RedisError as exc:
            await logger.awarning("pending-hide-message-add-failed", error=str(exc))

    def get(self, token: str) -> PendingHide | None:
        return self._hides.get(token)

    async def messages(self, token: str) -> set[int]:
        """Сообщения конфига: из памяти и из Redis (после рестарта память пуста)."""
        found = set(self._messages.get(token, ()))
        if self._redis is not None:
            try:
                found |= {int(value) for value in await self._redis.smembers(_MESSAGES_KEY.format(token=token))}
            except RedisError as exc:
                await logger.awarning("pending-hide-messages-load-failed", error=str(exc))
        return found

    async def forget_message(self, token: str, message_id: int) -> None:
        """Сообщение удалено - при повторной попытке скрытия его уже не трогаем."""
        self._messages.get(token, set()).discard(message_id)
        if self._redis is None:
            return
        try:
            await self._redis.srem(_MESSAGES_KEY.format(token=token), message_id)
        except RedisError as exc:
            await logger.awarning("pending-hide-message-remove-failed", error=str(exc))

    async def remove(self, token: str) -> None:
        """Снять запись. Вызывать только когда все сообщения конфига удалены - иначе рестарт их потеряет."""
        self._hides.pop(token, None)
        self._messages.pop(token, None)
        if self._redis is None:
            return
        try:
            await self._redis.hdel(_KEY, token)
            await self._redis.delete(_MESSAGES_KEY.format(token=token))
        except RedisError as exc:
            await logger.awarning("pending-hide-remove-failed", error=str(exc))

    async def load_all(self) -> list[PendingHide]:
        """Все записи из Redis, без очистки: каждую снимает успешное скрытие."""
        if self._redis is None:
            return list(self._hides.values())
        try:
            raw = await self._redis.hgetall(_KEY)
        except RedisError as exc:
            await logger.aerror("pending-hides-load-failed", error=str(exc))
            return list(self._hides.values())
        hides: dict[str, PendingHide] = dict(self._hides)
        for token, value in raw.items():
            try:
                hide = PendingHide(**json.loads(value))
            except (TypeError, ValueError) as exc:
                # Неразборчивую запись не скрыть никогда - убираем, чтобы она не всплывала на каждом старте.
                await logger.aerror("pending-hide-broken", token=token, error=str(exc))
                await self._redis.hdel(_KEY, token)
                continue
            hides.setdefault(hide.token, hide)
        return list(hides.values())

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()


_registry: PendingHides | None = None


async def close_pending_hides() -> None:
    if _registry is not None:
        await _registry.close()


def get_pending_hides() -> PendingHides:
    """Синглтон: клиент Redis создаётся при первом обращении и подключается лениво."""
    global _registry
    if _registry is None:
        _registry = PendingHides(Redis.from_url(settings.redis.URL) if settings.redis.USE_REDIS else None)
    return _registry
