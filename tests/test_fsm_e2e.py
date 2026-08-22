from __future__ import annotations

from typing import Any

from sqlalchemy import text

from tests.conftest import (  # noqa: F401
    _cb_update,
    _fsm,
    _msg_update,
    _seed_service_and_slot,
)


async def test_fsm_booking_flow_happy_path(env: Any) -> None:
    db, dp, bot, session = env
    service_id, slot_id = await _seed_service_and_slot(db)

    await dp.feed_update(bot, _cb_update(1, 42, f"book:slot:{service_id}:{slot_id}"))
    state = _fsm(dp, bot, 42)
    assert await state.get_state() is not None  # entered waiting_phone

    await dp.feed_update(bot, _msg_update(2, 42, "+79001234567"))
    assert "SendMessage" in session.calls
    async with db.session() as conn:
        row = await conn.execute(text("SELECT client_phone FROM bookings WHERE client_user_id = 42"))
        phone = row.scalar_one_or_none()
    assert phone == "+79001234567"
    state = _fsm(dp, bot, 42)
    assert await state.get_state() is None  # cleared after success


async def test_fsm_double_book_via_ui(env: Any) -> None:
    db, dp, bot, session = env
    service_id, slot_id = await _seed_service_and_slot(db)

    await dp.feed_update(bot, _cb_update(1, 42, f"book:slot:{service_id}:{slot_id}"))
    await dp.feed_update(bot, _msg_update(2, 42, "+79001234567"))

    await dp.feed_update(bot, _cb_update(3, 43, f"book:slot:{service_id}:{slot_id}"))
    await dp.feed_update(bot, _msg_update(4, 43, "+79005556677"))

    async with db.session() as conn:
        row = await conn.execute(text("SELECT COUNT(*) FROM bookings WHERE client_user_id = 43"))
        count = int(row.scalar_one())
    assert count == 0  # second user must not get a booking on the same slot
