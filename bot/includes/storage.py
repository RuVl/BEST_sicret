import pickle
from datetime import timedelta
from typing import Any

from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType
from aiogram.fsm.storage.redis import DefaultKeyBuilder, RedisStorage
from redis.asyncio import Redis

from env import RedisKeys


class PickleRedisStorage(RedisStorage):
	async def set_state(self, key: StorageKey, state: StateType = None) -> None:
		redis_key = self.key_builder.build(key, "state")
		if state is None:
			await self.redis.delete(redis_key)
		else:
			await self.redis.set(redis_key, state.state)

	async def get_state(self, key: StorageKey) -> str | None:
		redis_key = self.key_builder.build(key, "state")
		state = await self.redis.get(redis_key)
		return state.decode("utf-8") if state else None

	async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
		""" Сохраняет data как сериализованный """
		redis_key = self.key_builder.build(key, "data")
		if not data:
			await self.redis.delete(redis_key)
			return
		await self.redis.set(redis_key, pickle.dumps(data), ex=self.data_ttl, )

	async def get_data(self, key: StorageKey) -> dict[str, Any]:
		""" Загружает и десериализует """
		redis_key = self.key_builder.build(key, "data")
		raw = await self.redis.get(redis_key)
		return pickle.loads(raw) if raw else {}


def get_storage(
		*,
		cls=RedisStorage,
		state_ttl: timedelta | int | None = None,
		data_ttl: timedelta | int | None = None,
		key_builder_prefix: str = 'fsm',
		key_builder_separator: str = ':',
		key_builder_with_bot_id: bool = False,
		key_builder_with_destiny: bool = False,
		with_destiny: bool = False,
) -> BaseStorage:
	return cls(
		get_redis(),
		key_builder=DefaultKeyBuilder(
			prefix=key_builder_prefix,
			separator=key_builder_separator,
			with_bot_id=key_builder_with_bot_id,
			with_destiny=key_builder_with_destiny or with_destiny
		),
		state_ttl=state_ttl,
		data_ttl=data_ttl,
	)


def get_redis(**kwargs) -> Redis:
	return Redis.from_url(RedisKeys.URL, **kwargs)
