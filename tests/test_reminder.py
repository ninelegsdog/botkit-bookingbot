from datetime import datetime, timedelta

import pytest
from sqlalchemy.pool import StaticPool

from src.core.database import Database
from src.core.migrations import MigrationRegistry
from src.booking.models import register_migrations


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
