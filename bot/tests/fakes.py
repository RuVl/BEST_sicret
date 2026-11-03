"""Двойники внешних сервисов для тестов: без сети, без Redis и без Telegram."""

from redis.exceptions import ConnectionError as RedisConnectionError


class FakeRedis:
    """Подмножество ``redis.asyncio.Redis``, которым пользуется бот. Значения - bytes, как у настоящего."""

    def __init__(self) -> None:
        self.hashes: dict[str, dict[bytes, bytes]] = {}
        self.sets: dict[str, set[bytes]] = {}
        self.down = False

    def _check(self) -> None:
        if self.down:
            raise RedisConnectionError("redis is down")

    @staticmethod
    def _b(value) -> bytes:
        return value if isinstance(value, bytes) else str(value).encode()

    async def hset(self, key, field, value):
        self._check()
        self.hashes.setdefault(key, {})[self._b(field)] = self._b(value)

    async def hdel(self, key, field):
        self._check()
        self.hashes.get(key, {}).pop(self._b(field), None)

    async def hgetall(self, key):
        self._check()
        return dict(self.hashes.get(key, {}))

    async def sadd(self, key, value):
        self._check()
        self.sets.setdefault(key, set()).add(self._b(value))

    async def srem(self, key, value):
        self._check()
        self.sets.get(key, set()).discard(self._b(value))

    async def smembers(self, key):
        self._check()
        return set(self.sets.get(key, set()))

    async def delete(self, key):
        self._check()
        self.hashes.pop(key, None)
        self.sets.pop(key, None)

    async def aclose(self):
        pass
