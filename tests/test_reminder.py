from datetime import date, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from src.booking import service
from src.booking.models import register_migrations
from src.core.database import Database
from src.core.migrations import MigrationRegistry
from src.reminder.scheduler import send_due_reminders
from src.reminder.service import create_reminder, get_due_reminders
from tests.conftest import _cb_update, _msg_update, _seed_service_and_slot


@pytest.fixture
async def db():
    registry = MigrationRegistry()
    register_migrations(registry)
    database = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await database.init_database(registry)
    yield database
    await database.dispose()


async def test_create_reminder(db):
    from src.reminder.service import create_reminder, get_due_reminders

    rid = await create_reminder(
        db,
        booking_id=1,
        user_id=123,
        fire_at=datetime.now() - timedelta(hours=1),
        reminder_text="Test reminder",
    )
    assert rid > 0

    due = await get_due_reminders(db)
    assert len(due) == 1
    assert due[0]["user_id"] == 123


async def test_mark_sent(db):
    from src.reminder.service import create_reminder, get_due_reminders, mark_sent

    rid = await create_reminder(
        db,
        booking_id=1,
        user_id=123,
        fire_at=datetime.now() - timedelta(hours=1),
        reminder_text="Test",
    )
    await mark_sent(db, rid)

    due = await get_due_reminders(db)
    assert len(due) == 0


async def test_get_due_empty(db):
    from src.reminder.service import get_due_reminders

    due = await get_due_reminders(db)
    assert due == []


async def test_schedule_reminder_creates_row(db: Database) -> None:
    service_id, slot_id = await _seed_service_and_slot(db)
    booking_id = await service.book_slot(
        db, service_id=service_id, slot_id=slot_id, user_id=7, name="T", phone="+70000000000"
    )

    rid = await service.schedule_reminder(db, booking_id)

    assert rid
    expected_fire = (datetime(2030, 1, 1, 10, 0) - timedelta(hours=service.REMINDER_LEAD_HOURS)).isoformat()
    async with db.session() as conn:
        row = (
            await conn.execute(
                text("SELECT booking_id, user_id, fire_at, text, is_active FROM reminders WHERE id = :id"),
                {"id": rid},
            )
        ).first()
    assert row is not None
    assert row[0] == booking_id
    assert row[1] == 7
    assert row[2] == expected_fire
    assert "Haircut" in str(row[3])
    assert row[4] == 1


async def test_near_booking_gets_no_reminder(db: Database) -> None:
    """Inside the lead window a reminder would fire immediately: it is not scheduled."""
    service_id, _ = await _seed_service_and_slot(db)
    async with db.transaction() as conn:
        await conn.execute(
            text("INSERT INTO slots (service_id, date, start_time, end_time) VALUES (:sid, :d, '00:01', '01:00')"),
            {"sid": service_id, "d": date.today().isoformat()},
        )
        slot_id = int((await conn.execute(text("SELECT id FROM slots ORDER BY id DESC LIMIT 1"))).scalar_one())
    booking_id = await service.book_slot(
        db, service_id=service_id, slot_id=slot_id, user_id=7, name="T", phone="+70000000000"
    )

    assert await service.schedule_reminder(db, booking_id) is None
    async with db.session() as conn:
        count = int((await conn.execute(text("SELECT COUNT(*) FROM reminders"))).scalar_one())
    assert count == 0


async def test_cancel_booking_deactivates_reminder(db: Database) -> None:
    service_id, slot_id = await _seed_service_and_slot(db)
    booking_id = await service.book_slot(
        db, service_id=service_id, slot_id=slot_id, user_id=7, name="T", phone="+70000000000"
    )
    rid = await service.schedule_reminder(db, booking_id)
    assert rid

    assert await service.cancel_booking(db, booking_id, 7) is True

    async with db.session() as conn:
        active = (await conn.execute(text("SELECT is_active FROM reminders WHERE id = :id"), {"id": rid})).scalar_one()
    assert active == 0


async def test_booking_flow_schedules_reminder(env: Any) -> None:
    db, dp, bot, _session = env
    service_id, slot_id = await _seed_service_and_slot(db)

    await dp.feed_update(bot, _cb_update(1, 42, f"book:slot:{service_id}:{slot_id}"))
    await dp.feed_update(bot, _msg_update(2, 42, "+79001234567"))

    async with db.session() as conn:
        row = (await conn.execute(text("SELECT booking_id, user_id, text FROM reminders"))).first()
    assert row is not None
    assert row[0] == 1
    assert row[1] == 42
    assert "Haircut" in str(row[2])


async def test_send_due_reminders_sends_and_marks(env: Any) -> None:
    db, _dp, bot, session = env
    await create_reminder(
        db, booking_id=1, user_id=42, fire_at=datetime.now() - timedelta(hours=1), reminder_text="Visit soon"
    )

    sent = await send_due_reminders(db, bot)

    assert sent == 1
    assert await get_due_reminders(db) == []
    assert "SendMessage" in session.calls


async def test_send_failure_keeps_reminder_due(env: Any) -> None:
    db, _dp, _bot, _session = env
    await create_reminder(
        db, booking_id=1, user_id=42, fire_at=datetime.now() - timedelta(hours=1), reminder_text="Visit soon"
    )

    class BlockedBot:
        async def send_message(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("bot was blocked by the user")

    sent = await send_due_reminders(db, BlockedBot())  # type: ignore[arg-type]

    assert sent == 0
    assert len(await get_due_reminders(db)) == 1
