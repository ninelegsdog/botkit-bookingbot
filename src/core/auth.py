from collections.abc import Callable
from functools import wraps
from typing import Any

from aiogram import Router
from aiogram.types import CallbackQuery, Message

# The gate lives in botkit-core and is re-exported rather than vendored. Five private
# copies meant five places for a security fix to land in only some of them; reminder's
# copy had already drifted into a different design. A re-export (not a subclass) keeps
# them from diverging again.
from botkit_core.admin import AdminGate as AdminGate

ADMIN_GATE_ATTR = "_admin_gate"
ROUTER_REQUIRES_ADMIN = "_requires_admin"



def mark_admin_router(router: Router) -> Router:
    setattr(router, ROUTER_REQUIRES_ADMIN, True)
    return router


def _user_id(event: Any) -> int | None:
    if isinstance(event, (Message, CallbackQuery)) and event.from_user:
        return event.from_user.id
    return None


def require_admin(gate: AdminGate) -> Callable[..., Any]:
    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        setattr(func, ADMIN_GATE_ATTR, True)

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            for arg in args:
                uid = _user_id(arg)
                if uid is not None:
                    if not gate.is_admin(uid):
                        if isinstance(arg, Message):
                            await arg.answer("⛔ Доступ запрещён.")
                        elif isinstance(arg, CallbackQuery):
                            await arg.answer("⛔ Доступ запрещён.", show_alert=True)
                        return None
                    return await func(*args, **kwargs)
            return None

        return wrapper

    return decorator
