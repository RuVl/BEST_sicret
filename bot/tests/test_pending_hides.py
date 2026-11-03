import asyncio

from includes.pending_hides import PendingHide, PendingHides
from tests.fakes import FakeRedis

HIDE = PendingHide(token="t1", user_id=1, chat_id=10, stack_id="s")


def run(coro):
    return asyncio.run(coro)


class TestPendingHides:
    def test_messages_survive_restart(self):
        redis = FakeRedis()

        async def scenario():
            before = PendingHides(redis)
            await before.add(HIDE)
            await before.add_message("t1", 100)
            await before.add_message("t1", 101)

            after = PendingHides(redis)  # новый процесс: память пуста
            return await after.load_all(), await after.messages("t1")

        hides, messages = run(scenario())
        assert hides == [HIDE]
        assert messages == {100, 101}

    def test_remove_clears_record_and_messages(self):
        redis = FakeRedis()

        async def scenario():
            hides = PendingHides(redis)
            await hides.add(HIDE)
            await hides.add_message("t1", 100)
            await hides.remove("t1")
            fresh = PendingHides(redis)
            return await fresh.load_all(), await fresh.messages("t1")

        assert run(scenario()) == ([], set())

    def test_forget_message(self):
        async def scenario():
            hides = PendingHides(FakeRedis())
            await hides.add(HIDE)
            await hides.add_message("t1", 100)
            await hides.add_message("t1", 101)
            await hides.forget_message("t1", 100)
            return await hides.messages("t1")

        assert run(scenario()) == {101}

    def test_memory_works_when_redis_is_down(self):
        # Redis недоступен: страховки от рестарта нет, но таймер всё равно знает, что удалять.
        redis = FakeRedis()
        redis.down = True

        async def scenario():
            hides = PendingHides(redis)
            await hides.add(HIDE)
            await hides.add_message("t1", 100)
            return hides.get("t1"), await hides.messages("t1"), await hides.load_all()

        assert run(scenario()) == (HIDE, {100}, [HIDE])

    def test_without_redis(self):
        async def scenario():
            hides = PendingHides(None)
            await hides.add(HIDE)
            await hides.add_message("t1", 7)
            return await hides.messages("t1"), await hides.load_all()

        assert run(scenario()) == ({7}, [HIDE])

    def test_broken_record_is_dropped(self):
        redis = FakeRedis()
        redis.hashes["awg:pending-hides"] = {b"bad": b"{not json"}

        async def scenario():
            hides = PendingHides(redis)
            return await hides.load_all()

        assert run(scenario()) == []
        assert redis.hashes["awg:pending-hides"] == {}
