"""Двойники внешних сервисов для тестов: без сети, без Redis и без Telegram."""

import json

import httpx
from py3xui import AsyncApi
from redis.exceptions import ConnectionError as RedisConnectionError
from sqlalchemy.exc import OperationalError


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


class FakeSessionMaker:
    """Замена ``async_session`` для джобов: помнит, что закоммичено, и умеет ронять коммит отдельной строки.

    ``fail_commit`` - предикат по строке, добавленной в сессию: ``True`` - коммит падает, как упал бы
    при сбое БД. Закоммиченные строки копятся в ``committed`` в порядке коммитов.
    """

    def __init__(self, fail_commit=lambda row: False) -> None:
        self.fail_commit = fail_commit
        self.committed: list = []

    def __call__(self) -> "_FakeSession":
        return _FakeSession(self)


class _FakeSession:
    def __init__(self, maker: FakeSessionMaker) -> None:
        self._maker = maker
        self._added: list = []

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *exc) -> None:
        self._added.clear()

    def add(self, row) -> None:
        self._added.append(row)

    async def commit(self) -> None:
        if any(self._maker.fail_commit(row) for row in self._added):
            raise OperationalError("UPDATE", {}, Exception("connection lost"))
        self._maker.committed.extend(self._added)
        self._added.clear()


class FakeL10n:
    """Возвращает ключ и аргументы: тесты джобов проверяют, что ушло, а не тексты из .ftl."""

    def format_value(self, key: str, args: dict | None = None) -> str:
        return f"{key} {args or ''}"


class FakeBot:
    """Подмножество ``aiogram.Bot`` для отправки: запоминает отправленное, ошибки - по chat_id."""

    def __init__(self, errors: dict[int, Exception] | None = None) -> None:
        self.errors = errors or {}
        self.sent: list[tuple[int, str]] = []

    async def send_message(self, chat_id: int, text: str, **kwargs):
        error = self.errors.get(chat_id)
        if error is not None:
            raise error
        self.sent.append((chat_id, text))


class FakePanel:
    """Панель 3x-ui за настоящим py3xui: подменён только транспорт httpx, разбор ответов - библиотечный.

    ``routes`` - ответы по префиксу пути после ``/panel/api``. Значение: ``obj`` успешного ответа,
    готовый ``httpx.Response`` или исключение транспорта. Запросы копятся в ``requests``.
    """

    def __init__(self, monkeypatch, routes: dict[str, object]) -> None:
        self._routes = routes
        self.requests: list[tuple[str, object]] = []
        real_client = httpx.AsyncClient

        def client_factory(**kwargs) -> httpx.AsyncClient:
            return real_client(transport=httpx.MockTransport(self._handle), **kwargs)

        monkeypatch.setattr(httpx, "AsyncClient", client_factory)
        self.api = AsyncApi("https://panel/base", token="token", timeout=15)
        self.api.max_retries = 1

    def _handle(self, request: httpx.Request) -> httpx.Response:
        path = request.url.raw_path.decode().split("/panel/api", 1)[1]
        self.requests.append((path, json.loads(request.content) if request.content else None))
        for prefix, answer in self._routes.items():
            if path.startswith(prefix):
                if isinstance(answer, Exception):
                    raise answer
                if isinstance(answer, httpx.Response):
                    return answer
                return httpx.Response(200, json={"success": True, "msg": "", "obj": answer})
        raise AssertionError(f"неожиданный запрос {path}")

    def body(self, prefix: str):
        return next(body for path, body in self.requests if path.startswith(prefix))


def panel_failure(msg: str) -> httpx.Response:
    """Ответ панели с ``success=false``: так она сообщает об отсутствующем клиенте и о дублях."""
    return httpx.Response(200, json={"success": False, "msg": msg, "obj": None})
