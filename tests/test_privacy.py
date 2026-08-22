from __future__ import annotations

import datetime
from typing import Any

import pytest
from aiogram import Bot
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.types import Update
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from src.app import collect_routers
from src.booking.models import register_migrations
from src.core.auth import AdminGate
from src.core.bot_factory import build_dispatcher
from src.core.database import Database
from src.core.migrations import MigrationRegistry
from src.core.navigation import NavRegistry
from tests.test_fsm_e2e import FakeSession, _msg_update


@pytest.fixture
async def privacy_env() -> Any:
    registry = MigrationRegistry()
    register_migrations(registry)
    database = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await database.init_database(registry)
    dp = build_dispatcher(
        routers=collect_routers(gate=AdminGate("pw"), nav=NavRegistry(), db=database),
        storage=None,
    )
    bot_obj = Bot(token="42:TEST_TOKEN", session=FakeSession())
    yield database, dp, bot_obj
    await bot_obj.session.close()
    await database.dispose()


async def _seed_two_users(db: Database) -> None:
    async with db.transaction() as conn:
        await conn.execute(text("INSERT INTO services (name) VALUES ('S')"))
        await conn.execute(
            text(
                "INSERT INTO slots (service_id, date, start_time, end_time) VALUES (1, '2030-01-01', '10:00', '11:00')"
            )
        )
        for uid in (42, 43):
            await conn.execute(
                text(
                    "INSERT INTO bookings (service_id, slot_id, client_user_id, client_name,"
                    " client_phone, booking_date, start_time) VALUES"
                    " (1, NULL, :uid, 'N', '+70000000000', '2030-01-01', '10:00')"
                ),
                {"uid": uid},
            )
            await conn.execute(
                text("INSERT INTO feedback (user_id, service_id, rating) VALUES (:uid, 1, 5)"),
                {"uid": uid},
            )


def _fsm(dp: Any, bot: Any, uid: int) -> FSMContext:
    return FSMContext(storage=dp.storage, key=StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid))


async def test_delete_my_data_deletes_only_own_rows(privacy_env: Any) -> None:
    db, dp, bot = privacy_env
    await _seed_two_users(db)

    upd1 = _msg_update(1, 42, "/delete_my_data")
    assert isinstance(upd1, Update)
    await dp.feed_update(bot, upd1)

    confirm = Update(
        update_id=2,
        callback_query=_make_confirm(2, 42, "privacy:confirm"),
    )
    await dp.feed_update(bot, confirm)

    async with db.session() as conn:
        left_42 = int((await conn.execute(text("SELECT COUNT(*) FROM bookings WHERE client_user_id=42"))).scalar_one())
        fb_42 = int((await conn.execute(text("SELECT COUNT(*) FROM feedback WHERE user_id=42"))).scalar_one())
        left_43 = int((await conn.execute(text("SELECT COUNT(*) FROM bookings WHERE client_user_id=43"))).scalar_one())
        audit = (await conn.execute(text("SELECT action FROM audit_log WHERE client_user_id=42"))).scalar_one()
    assert left_42 == 0 and fb_42 == 0
    assert left_43 == 1
    assert audit == "delete_my_data"


async def test_privacy_cancel_keeps_data(privacy_env: Any) -> None:
    db, dp, bot = privacy_env
    await _seed_two_users(db)
    await dp.feed_update(bot, _msg_update(1, 42, "/delete_my_data"))
    await dp.feed_update(bot, Update(update_id=2, callback_query=_make_confirm(2, 42, "privacy:cancel")))
    async with db.session() as conn:
        left = int((await conn.execute(text("SELECT COUNT(*) FROM bookings WHERE client_user_id=42"))).scalar_one())
    assert left == 1


def _make_confirm(update_id: int, uid: int, data: str) -> Any:
    from aiogram.types import CallbackQuery, Chat, Message, User

    msg = Message(
        message_id=update_id,
        date=datetime.datetime.now(tz=datetime.UTC),
        chat=Chat(id=uid, type="private"),
        from_user=User(id=uid, first_name="T", is_bot=False),
    )
    return CallbackQuery(
        id=f"c{update_id}",
        from_user=User(id=uid, first_name="T", is_bot=False),
        chat_instance="ci",
        data=data,
        message=msg,
    )
