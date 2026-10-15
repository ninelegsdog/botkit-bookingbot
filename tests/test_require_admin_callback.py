"""require_admin must gate CallbackQuery, not only Message.

The admin menu is inline: every admin action arrives as a CallbackQuery. A
``_user_id`` that only understood ``Message`` returned ``None`` for a callback,
so the wrapper fell through to ``return None`` and the handler never ran - the
admin buttons were silently dead while the message commands worked.

A test that unwraps the decorator (reaches into ``__closure__``) exercises the
inner function and cannot see this, which is why the buttons stayed broken under
a green suite. These tests call the wrapper that aiogram actually registers.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram import Bot, Dispatcher, F, Router
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import CallbackQuery, Message, Update, User

from src.core.auth import AdminGate, require_admin


def _user(uid: int) -> Any:
    u = MagicMock()
    u.id = uid
    return u


def _message(uid: int) -> Any:
    m = MagicMock(spec=Message)
    m.from_user = _user(uid)
    m.answer = AsyncMock()
    m.edit_text = AsyncMock()
    return m


def _callback(uid: int, data: str = "adm:x") -> Any:
    c = MagicMock(spec=CallbackQuery)
    c.from_user = _user(uid)
    c.data = data
    c.answer = AsyncMock()
    c.message = _message(uid)
    return c


@pytest.fixture
def gate() -> AdminGate:
    return AdminGate(password="secret", admin_ids=[456])


async def test_callback_from_admin_reaches_handler(gate: AdminGate) -> None:
    seen: list[int] = []

    @require_admin(gate)
    async def handler(cb: Any) -> str:
        seen.append(cb.from_user.id)
        return "ran"

    assert await handler(_callback(456)) == "ran"
    assert seen == [456]


async def test_callback_from_non_admin_is_blocked(gate: AdminGate) -> None:
    seen: list[int] = []

    @require_admin(gate)
    async def handler(cb: Any) -> str:
        seen.append(1)
        return "ran"

    cb = _callback(999)
    assert await handler(cb) is None
    assert seen == []
    cb.answer.assert_awaited(), "a blocked callback must be answered, not left spinning"


async def test_message_from_admin_reaches_handler(gate: AdminGate) -> None:
    seen: list[int] = []

    @require_admin(gate)
    async def handler(msg: Any) -> str:
        seen.append(msg.from_user.id)
        return "ran"

    assert await handler(_message(456)) == "ran"
    assert seen == [456]


async def test_message_from_non_admin_is_blocked(gate: AdminGate) -> None:
    seen: list[int] = []

    @require_admin(gate)
    async def handler(msg: Any) -> str:
        seen.append(1)
        return "ran"

    msg = _message(999)
    assert await handler(msg) is None
    assert seen == []
    msg.answer.assert_awaited()


async def test_router_registered_wrapper_gates_callback(gate: AdminGate) -> None:
    """The callback aiogram registers (the wrapper, not the inner) must run for an admin.

    Breaking ``_user_id`` so it ignores CallbackQuery makes the first call return
    ``None`` and ``seen`` stay empty - which is exactly the bug this guards.
    """
    router = Router()
    seen: list[int] = []

    @router.callback_query(F.data == "adm:x")
    @require_admin(gate)
    async def panel(cb: Any) -> None:
        seen.append(cb.from_user.id)

    registered = router.callback_query.handlers[0].callback
    await registered(_callback(456, data="adm:x"))
    assert seen == [456], "an authorised admin's callback must reach the handler"

    await registered(_callback(999, data="adm:x"))
    assert seen == [456], "a non-admin's callback must not reach the handler"


async def test_wrapper_survives_real_dispatch(gate: AdminGate) -> None:
    """aiogram must be able to call the wrapper it registered.

    The wrapper is written `(*args, **kwargs)`. aiogram reads that signature and,
    because it accepts **kwargs, forwards the whole dispatcher context (dispatcher,
    bot, state, ...) to the decorated function - which then raises TypeError for
    every unexpected keyword. ``functools.wraps(func)`` makes aiogram see the real
    signature and filter the kwargs. A test that calls the handler directly cannot
    see this; only the dispatcher can.
    """
    router = Router()
    seen: list[int] = []

    @router.callback_query(F.data == "adm:x")
    @require_admin(gate)
    async def panel(cb: Any) -> None:
        seen.append(cb.from_user.id)

    bot = Bot(token="123456789:AAfake")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    async def feed(uid: int) -> None:
        cb = CallbackQuery(
            id="1",
            from_user=User(id=uid, is_bot=False, first_name="A"),
            chat_instance="ci",
            data="adm:x",
        )
        with patch.object(bot.session, "make_request", new_callable=AsyncMock):
            await dp.feed_update(bot, Update(update_id=1, callback_query=cb))

    await feed(456)
    assert seen == [456], "an admin callback must reach the handler through the dispatcher"

    await feed(999)
    assert seen == [456], "a non-admin callback must not reach the handler"
