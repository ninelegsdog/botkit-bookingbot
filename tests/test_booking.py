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


async def test_get_active_services_empty(db):
    from src.booking.service import get_active_services

    result = await get_active_services(db)
    assert result == []


async def test_get_service_not_found(db):
    from src.booking.service import get_service

    result = await get_service(db, 999)
    assert result is None


async def test_get_free_slots_empty(db):
    from src.booking.service import get_free_slots

    result = await get_free_slots(db, 1, "2026-01-01")
    assert result == []


async def test_cancel_booking_not_found(db):
    from src.booking.service import cancel_booking

    result = await cancel_booking(db, 999, 123)
    assert result is False


async def test_get_user_bookings_empty(db):
    from src.booking.service import get_user_bookings

    result = await get_user_bookings(db, 123)
    assert result == []


async def test_book_slot_raises_on_missing(db):
    from src.booking.service import book_slot, SlotUnavailableError

    with pytest.raises(SlotUnavailableError):
        await book_slot(db, service_id=999, slot_id=999, user_id=1, name="Test", phone="+7000")


async def test_get_available_dates_no_service(db):
    from src.booking.service import get_available_dates

    result = await get_available_dates(db, 999)
    assert result == []


async def test_get_schedule_empty(db):
    from src.booking.service import get_schedule

    result = await get_schedule(db, 0)
    assert result == []
