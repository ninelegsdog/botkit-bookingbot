import time
from collections.abc import Callable
from typing import Any

import redis.asyncio as redis
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, redis_url: str, rate_limit: float = 0.5, max_idle: float = 60.0) -> None:
        self._redis = redis.from_url(redis_url, decode_responses=True)
        self._rate_limit = rate_limit
        self._max_idle = max_idle
        self._local_cache: dict[int, float] = {}

    async def __call__(self, handler: Callable[..., Any], event: TelegramObject, data: dict[str, Any]) -> Any:
        user_id = getattr(getattr(event, "from_user", None), "id", None)
        if user_id is None:
            return await handler(event, data)

        now = time.time()

        # Check local cache first
        last = self._local_cache.get(user_id, 0)
        if now - last < self._rate_limit:
            try:
                redis_last = await self._redis.get(f"throttle:{user_id}")
                if redis_last and now - float(redis_last) < self._rate_limit:
                    return None
            except Exception:
                pass

        self._local_cache[user_id] = now
        try:
            await self._redis.set(f"throttle:{user_id}", str(now), ex=int(self._max_idle))
        except Exception:
            pass
        return await handler(event, data)
