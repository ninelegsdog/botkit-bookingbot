from __future__ import annotations

import datetime
from typing import Any

from aiogram.types import Message, SuccessfulPayment, Update
from sqlalchemy import text

from tests.conftest import (
    _cb_update,
    _msg_update,
    _seed_service_and_slot,
)


def _paid_update(update_id: int, uid: int, payload: str) -> Update:
    sp = SuccessfulPayment(
        currency="XTR",
        total_amount=500,
        invoice_payload=payload,
        telegram_payment_charge_id=f"chg{update_id}",
        provider_payment_charge_id="prov1",
    )
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.datetime.now(tz=datetime.UTC),
            chat=_chat(uid),
            from_user=_user(uid),
            successful_payment=sp,
        ),
    )


# reuse chat/user builders from fsm module
from aiogram.types import Chat as _Chat  # noqa: E402
from aiogram.types import User as _User  # noqa: E402


def _chat(uid: int) -> Any:
    return _Chat(id=uid, type="private")


def _user(uid: int) -> Any:
    return _User(id=uid, first_name="T", is_bot=False)


async def test_deposit_flow_books_then_marks_paid(env: Any) -> None:
    db, dp, bot, session = env
    service_id, slot_id = await _seed_service_and_slot(db)

    await dp.feed_update(bot, _cb_update(1, 42, f"book:slot:{service_id}:{slot_id}"))
    await dp.feed_update(bot, _msg_update(2, 42, "+79001234567"))

    async with db.session() as conn:
        bid = int((await conn.execute(text("SELECT id FROM bookings"))).scalar_one())
        status_row = await conn.execute(text("SELECT status FROM bookings"))
        assert status_row.scalar_one() == "confirmed"

    await dp.feed_update(bot, _paid_update(3, 42, f"deposit:{bid}"))

    async with db.session() as conn:
        status_row = await conn.execute(text("SELECT status FROM bookings WHERE id = :bid"), {"bid": bid})
        status_after = status_row.scalar_one()
    assert status_after == "paid"


async def test_wrong_payload_ignored(env: Any) -> None:
    db, dp, bot, session = env
    service_id, slot_id = await _seed_service_and_slot(db)
    await dp.feed_update(bot, _cb_update(1, 42, f"book:slot:{service_id}:{slot_id}"))
    await dp.feed_update(bot, _msg_update(2, 42, "+79001234567"))
    await dp.feed_update(bot, _paid_update(3, 42, "deposit:not-a-number"))
    async with db.session() as conn:
        statuses = (await conn.execute(text("SELECT status FROM bookings"))).all()
    assert len(statuses) == 1 and statuses[0][0] == "confirmed"
