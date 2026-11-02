"""Незавершённые таймеры автоскрытия конфигов AmneziaWG - чтобы их не терял перезапуск бота.

Таймер живёт в памяти процесса: после рестарта (деплой) сообщение с конфигом, то есть
с приватным ключом, осталось бы в чате, пока человек сам не нажмёт кнопку, а через 48 часов
Telegram его уже не даст удалить. Поэтому каждый таймер записан в Redis, и при старте бот
скрывает всё, что не успел: байтов конфига в памяти к этому моменту всё равно нет.

Без Redis (``USE_REDIS=False``) запись выключена: тогда и стек диалогов после рестарта пропадает.
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


@dataclass(frozen=True)
class PendingHide:
    """Окно с конфигом, которое ещё надо скрыть: по этим полям бот находит стек диалога."""

    token: str
    user_id: int
    chat_id: int
    stack_id: str


class PendingHides:
    def __init__(self, redis: Redis | None) -> None:
        self._redis = redis

    async def add(self, hide: PendingHide) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.hset(_KEY, hide.token, json.dumps(asdict(hide)))
        except RedisError as exc:
            # Конфиг всё равно покажем и скроем по таймеру - теряется только страховка от рестарта.
            await logger.awarning("pending-hide-add-failed", error=str(exc))

    async def remove(self, token: str) -> None:
        if self._redis is None:
            return
        try:
            await self._redis.hdel(_KEY, token)
        except RedisError as exc:
            await logger.awarning("pending-hide-remove-failed", error=str(exc))

    async def take_all(self) -> list[PendingHide]:
        """Все записи разом, с очисткой: при старте каждую обрабатываем один раз."""
        if self._redis is None:
            return []
        try:
            raw = await self._redis.hgetall(_KEY)
            await self._redis.delete(_KEY)
        except RedisError as exc:
            await logger.aerror("pending-hides-load-failed", error=str(exc))
            return []
        hides = []
        for value in raw.values():
            try:
                hides.append(PendingHide(**json.loads(value)))
            except (TypeError, ValueError) as exc:
                await logger.awarning("pending-hide-broken", error=str(exc))
        return hides

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
