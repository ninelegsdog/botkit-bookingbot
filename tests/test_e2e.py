import pytest
from sqlalchemy import text
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


async def test_full_booking_flow(db):
    from src.booking import service

    # Insert test service
    async with db.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (name, duration_min, price) VALUES ('Haircut', 30, 500)")
        )

    # Verify service created
    services = await service.get_active_services(db)
    assert len(services) == 1
    assert services[0]["name"] == "Haircut"
    assert services[0]["duration_min"] == 30
    assert services[0]["price"] == 500

    # Get service details
    svc = await service.get_service(db, services[0]["id"])
    assert svc is not None
    assert svc["name"] == "Haircut"

    # No schedule → no available dates
    dates = await service.get_available_dates(db, services[0]["id"])
    assert dates == []


async def test_service_deactivation(db):
    from src.booking import service

    async with db.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (name, duration_min, price, is_active) VALUES ('Old', 60, 0, 0)")
        )

    services = await service.get_active_services(db)
    assert len(services) == 0


async def test_cancellation_flow(db):
    from src.booking import service

    # Create service
    async with db.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (name, duration_min, price) VALUES ('Test', 60, 100)")
        )

    # Create a slot
    async with db.transaction() as conn:
        await conn.execute(
            text(
                "INSERT INTO slots (service_id, date, start_time, end_time, is_booked) "
                "VALUES (1, '2099-01-01', '10:00', '11:00', 0)"
            )
        )

    # Book it
    booking_id = await service.book_slot(
        db, service_id=1, slot_id=1, user_id=123, name="Test", phone="+7000"
    )
    assert booking_id > 0

    # Verify booked
    bookings = await service.get_user_bookings(db, 123)
    assert len(bookings) == 1
    assert bookings[0]["status"] == "confirmed"

    # Cancel
    ok = await service.cancel_booking(db, booking_id, 123)
    assert ok is True

    # Verify cancelled
    bookings = await service.get_user_bookings(db, 123)
    assert len(bookings) == 0


async def test_double_booking_prevention(db):
    from src.booking import service
    from src.booking.service import SlotUnavailableError

    async with db.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (name, duration_min, price) VALUES ('Test', 60, 100)")
        )
        await conn.execute(
            text(
                "INSERT INTO slots (service_id, date, start_time, end_time, is_booked) "
                "VALUES (1, '2099-01-01', '10:00', '11:00', 0)"
            )
        )

    # First booking succeeds
    await service.book_slot(db, service_id=1, slot_id=1, user_id=100, name="A", phone="+7001")

    # Second booking fails
    with pytest.raises(SlotUnavailableError):
        await service.book_slot(db, service_id=1, slot_id=1, user_id=200, name="B", phone="+7002")


async def test_wrong_user_cancel(db):
    from src.booking import service

    async with db.transaction() as conn:
        await conn.execute(
            text("INSERT INTO services (name, duration_min, price) VALUES ('Test', 60, 100)")
        )
        await conn.execute(
            text(
                "INSERT INTO slots (service_id, date, start_time, end_time, is_booked) "
                "VALUES (1, '2099-01-01', '10:00', '11:00', 0)"
            )
        )

    booking_id = await service.book_slot(
        db, service_id=1, slot_id=1, user_id=100, name="A", phone="+7001"
    )

    # Wrong user tries to cancel
    ok = await service.cancel_booking(db, booking_id, 999)
    assert ok is False
