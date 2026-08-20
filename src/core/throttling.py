import time
from collections.abc import Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject


class ThrottlingMiddleware(BaseMiddleware):
    def __init__(self, rate_limit: float = 0.5, max_idle: float = 60.0) -> None:
        self._rate_limit = rate_limit
        self._max_idle = max_idle
        self._last_message: dict[int, float] = {}

    async def __call__(self, handler: Callable[..., Any], event: TelegramObject, data: dict[str, Any]) -> Any:
        user_id = getattr(getattr(event, "from_user", None), "id", None)
        if user_id is None:
            return await handler(event, data)

        now = time.time()
        last = self._last_message.get(user_id, 0)
        if now - last < self._rate_limit:
            return None

        self._last_message[user_id] = now
        self._prune(now)
        return await handler(event, data)

    def _prune(self, now: float) -> None:
        expired = [uid for uid, ts in self._last_message.items() if now - ts > self._max_idle]
        for uid in expired:
            del self._last_message[uid]
