import time
from collections.abc import Callable
from typing import Any

from aiogram import Router
from aiogram.types import Message

ADMIN_GATE_ATTR = "_admin_gate"
ROUTER_REQUIRES_ADMIN = "_requires_admin"


class AdminGate:
    def __init__(self, password: str) -> None:
        self._password = password
        self._authorized: set[int] = set()
        self._attempts: dict[int, list[float]] = {}
        self._throttle_window = 300.0
        self._max_attempts = 5

    def is_admin(self, user_id: int) -> bool:
        return user_id in self._authorized

    def authorize(self, user_id: int, password: str) -> bool:
        if password != self._password:
            now = time.time()
            attempts = self._attempts.setdefault(user_id, [])
            attempts[:] = [t for t in attempts if now - t < self._throttle_window]
            attempts.append(now)
            return False
        self._authorized.add(user_id)
        self._attempts.pop(user_id, None)
        return True

    def deauthorize(self, user_id: int) -> None:
        self._authorized.discard(user_id)

    def is_throttled(self, user_id: int) -> bool:
        now = time.time()
        attempts = self._attempts.get(user_id, [])
        attempts[:] = [t for t in attempts if now - t < self._throttle_window]
        return len(attempts) >= self._max_attempts


def mark_admin_router(router: Router) -> Router:
    setattr(router, ROUTER_REQUIRES_ADMIN, True)
    return router


def _user_id(event: Any) -> int | None:
    if isinstance(event, Message) and event.from_user:
        return event.from_user.id
    return None


def require_admin(gate: AdminGate) -> Callable:
    def decorator(func: Callable) -> Callable:
        setattr(func, ADMIN_GATE_ATTR, True)

        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for arg in args:
                uid = _user_id(arg)
                if uid is not None:
                    if not gate.is_admin(uid):
                        if isinstance(arg, Message):
                            await arg.answer("⛔ Доступ запрещён.")
                        return None
                    return await func(*args, **kwargs)
            return None

        return wrapper

    return decorator
