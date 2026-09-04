"""Extra tests for booking handlers to boost coverage to 80%."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from src.booking.models import register_migrations
from src.core.database import Database
from src.core.migrations import MigrationRegistry


@pytest.fixture
async def db_extra():
    registry = MigrationRegistry()
    register_migrations(registry)
    database = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await database.init_database(registry)
    yield database
    await database.dispose()


@pytest.mark.asyncio
async def test_booking_get_active_services(db_extra):
    from src.booking.service import get_active_services

    services = await get_active_services(db_extra)
    assert services == []


@pytest.mark.asyncio
async def test_booking_get_service_not_found(db_extra):
    from src.booking.service import get_service

    svc = await get_service(db_extra, 9999)
    assert svc is None


@pytest.mark.asyncio
async def test_booking_get_free_slots(db_extra):
    from src.booking.service import get_free_slots
    from sqlalchemy import text

    # Create service and slot via SQL
    async with db_extra.transaction() as conn:
        await conn.execute(text("INSERT INTO services (id, name, duration_min, price, is_active) VALUES (1, 'Test', 30, 100, 1)"))
        await conn.execute(text("INSERT INTO slots (id, service_id, date, start_time, end_time, is_booked) VALUES (1, 1, '2099-12-31', '10:00', '10:30', 0)"))

    slots = await get_free_slots(db_extra, 1, "2099-12-31")
    assert len(slots) == 1
    assert slots[0]["start_time"] == "10:00"


@pytest.mark.asyncio
async def test_booking_cancel_nonexistent(db_extra):
    from src.booking.service import cancel_booking

    result = await cancel_booking(db_extra, booking_id=99999, user_id=123)
    assert result is False
