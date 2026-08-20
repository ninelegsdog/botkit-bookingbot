from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage


def create_storage(redis_url: str | None) -> BaseStorage:
    if redis_url:
        try:
            import redis.asyncio as aioredis
            from aiogram.fsm.storage.redis import RedisStorage

            redis = aioredis.from_url(redis_url)
            return RedisStorage(redis=redis)
        except ImportError:
            pass
    return MemoryStorage()
