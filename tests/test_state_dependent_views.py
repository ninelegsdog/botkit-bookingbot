"""State-dependent view tests for bookingbot."""

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
async def test_services_empty_vs_populated(db_extra):
    from src.booking.service import get_active_services

    assert await get_active_services(db_extra) == []

    async with db_extra.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (id, name, duration_min, price, is_active) VALUES (1, 'Cut', 30, 100, 1)")
        )
    services = await get_active_services(db_extra)
    assert len(services) == 1
    assert services[0]["name"] == "Cut"


@pytest.mark.asyncio
async def test_service_missing_vs_present(db_extra):
    from src.booking.service import get_service

    assert await get_service(db_extra, 9999) is None

    async with db_extra.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (id, name, duration_min, price, is_active) VALUES (1, 'Cut', 30, 100, 1)")
        )
    svc = await get_service(db_extra, 1)
    assert svc is not None
    assert svc["name"] == "Cut"


@pytest.mark.asyncio
async def test_free_slots_empty_vs_available(db_extra):
    from src.booking.service import get_free_slots

    async with db_extra.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (id, name, duration_min, price, is_active) VALUES (1, 'Cut', 30, 100, 1)")
        )
        await conn.execute(
            text(
                "INSERT INTO slots (id, service_id, date, start_time, end_time, is_booked) "
                "VALUES (1, 1, '2099-12-31', '10:00', '10:30', 0)"
            )
        )

    slots = await get_free_slots(db_extra, 1, "2099-12-31")
    assert len(slots) == 1

    empty = await get_free_slots(db_extra, 1, "2000-01-01")
    assert empty == []


@pytest.mark.asyncio
async def test_user_bookings_empty_vs_populated(db_extra):
    from src.booking.service import get_user_bookings

    assert await get_user_bookings(db_extra, 123) == []

    async with db_extra.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (id, name, duration_min, price, is_active) VALUES (1, 'Cut', 30, 100, 1)")
        )
        await conn.execute(
            text(
                "INSERT INTO slots (id, service_id, date, start_time, end_time, is_booked) "
                "VALUES (1, 1, '2099-12-31', '10:00', '10:30', 0)"
            )
        )
        await conn.execute(
            text(
                "INSERT INTO bookings (id, service_id, slot_id, client_user_id, client_name, "
                "client_phone, booking_date, start_time, status) "
                "VALUES (1, 1, 1, 123, 'U', '123', '2099-12-31', '10:00', 'confirmed')"
            )
        )

    bookings = await get_user_bookings(db_extra, 123)
    assert len(bookings) == 1


@pytest.mark.asyncio
async def test_cancel_booking_nonexistent(db_extra):
    from src.booking.service import cancel_booking

    result = await cancel_booking(db_extra, booking_id=99999, user_id=123)
    assert result is False
