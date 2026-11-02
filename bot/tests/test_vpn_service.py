import asyncio
import json
from types import SimpleNamespace

import pytest

from includes.pending_hides import PendingHide, PendingHides
from includes.vpn import ClientDetails, XuiClient, XuiError
from includes.vpn import service as vpn_service
from utils import split_message


class _HangingSession:
    """aiohttp-сессия, у которой истёк общий таймаут: aiohttp бросает голый TimeoutError."""

    closed = False

    def request(self, *args, **kwargs):
        raise TimeoutError


class TestPanelTimeout:
    def test_total_timeout_is_a_panel_error(self):
        # Иначе исключение пролетает мимо except XuiError в джобах и диалогах.
        client = XuiClient("https://panel", "token", "https://sub")
        client._session = _HangingSession()

        with pytest.raises(XuiError, match="не ответила"):
            asyncio.run(client.get_client_details("ivan@best-eu.org"))


def _details(**client) -> ClientDetails:
    return ClientDetails.model_validate({"client": {"email": "ivan@best-eu.org", "uuid": "u1", "subId": "s1"} | client})


class _Panel:
    def __init__(self, clients: dict[str, ClientDetails]):
        self._clients = clients

    async def get_client_details(self, email: str) -> ClientDetails | None:
        return self._clients.get(email)


def _resolve(monkeypatch, known_person_id: int | None, **client) -> str:
    async def get_subscription_by_email(session, email):
        return None if known_person_id is None else SimpleNamespace(person_id=known_person_id)

    monkeypatch.setattr(vpn_service, "get_subscription_by_email", get_subscription_by_email)
    person = SimpleNamespace(id=7, telegram_id=100, full_name="Иванов Иван")
    member = SimpleNamespace(best_email="ivan@best-eu.org", full_name_ru="Иванов Иван")
    panel = _Panel({"ivan@best-eu.org": _details(**client)})
    email, _ = asyncio.run(vpn_service._resolve_target(None, panel, person, member))
    return email


class TestResolveTarget:
    def test_own_subscription_is_adopted(self, monkeypatch):
        assert _resolve(monkeypatch, known_person_id=7) == "ivan@best-eu.org"

    def test_subscription_of_another_person_is_not_taken(self, monkeypatch):
        # Сменил Telegram-аккаунт или дубль почты в таблице: чужую строку не переписываем.
        assert _resolve(monkeypatch, known_person_id=8, tgId=100) == "lbg-7"

    def test_manual_client_of_same_person_is_adopted(self, monkeypatch):
        assert _resolve(monkeypatch, known_person_id=None, tgId=100, comment="Иванов Иван") == "ivan@best-eu.org"

    def test_manual_client_of_someone_else_is_not_taken(self, monkeypatch):
        assert _resolve(monkeypatch, known_person_id=None, tgId=555) == "lbg-7"


class TestPersonComment:
    def test_name_from_members_table_wins(self):
        person = SimpleNamespace(full_name="Ivan Ivanov")
        assert vpn_service.person_comment(person, SimpleNamespace(full_name_ru="Иванов Иван")) == "Иванов Иван"

    def test_falls_back_to_telegram_name(self):
        person = SimpleNamespace(full_name="Ivan Ivanov")
        assert vpn_service.person_comment(person, None) == "Ivan Ivanov"
        assert vpn_service.person_comment(person, SimpleNamespace(full_name_ru=None)) == "Ivan Ivanov"


class TestSplitMessage:
    def test_short_text_is_one_message(self):
        assert split_message("a\nb") == ["a\nb"]

    def test_splits_by_lines(self):
        text = "\n".join(["x" * 10] * 5)
        parts = split_message(text, limit=25)
        assert all(len(part) <= 25 for part in parts)
        assert "\n".join(parts) == text

    def test_long_line_is_not_cut_inside_escape(self):
        # «\.» - одна экранированная точка MarkdownV2: разрезать её нельзя.
        parts = split_message("ab\\.cd", limit=3)
        assert all(not part.endswith("\\") for part in parts)
        assert "".join(parts) == "ab\\.cd"


class _FakeRedis:
    def __init__(self):
        self.data: dict[str, dict[str, str]] = {}

    async def hset(self, key, field, value):
        self.data.setdefault(key, {})[field] = value

    async def hdel(self, key, field):
        self.data.get(key, {}).pop(field, None)

    async def hgetall(self, key):
        return dict(self.data.get(key, {}))

    async def delete(self, key):
        self.data.pop(key, None)


class TestPendingHides:
    def test_survives_restart_until_taken(self):
        redis = _FakeRedis()
        hide = PendingHide(token="t1", user_id=1, chat_id=2, stack_id="s")

        asyncio.run(PendingHides(redis).add(hide))
        # Новый процесс - новый объект, но записи в Redis на месте.
        assert asyncio.run(PendingHides(redis).take_all()) == [hide]
        assert asyncio.run(PendingHides(redis).take_all()) == []

    def test_finished_timer_is_forgotten(self):
        redis = _FakeRedis()
        registry = PendingHides(redis)
        asyncio.run(registry.add(PendingHide(token="t1", user_id=1, chat_id=2, stack_id="s")))
        asyncio.run(registry.remove("t1"))
        assert asyncio.run(registry.take_all()) == []

    def test_broken_record_is_skipped(self):
        redis = _FakeRedis()
        good = json.dumps({"token": "ok", "user_id": 1, "chat_id": 2, "stack_id": "s"})
        redis.data["awg:pending-hides"] = {"bad": "{}", "ok": good}
        assert [hide.token for hide in asyncio.run(PendingHides(redis).take_all())] == ["ok"]

    def test_without_redis_nothing_is_stored(self):
        registry = PendingHides(None)
        asyncio.run(registry.add(PendingHide(token="t1", user_id=1, chat_id=2, stack_id="s")))
        assert asyncio.run(registry.take_all()) == []
