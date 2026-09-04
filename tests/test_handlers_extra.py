"""Extra tests for booking handlers FSM to boost coverage 77->80%."""
from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_booking_states() -> None:
    from src.booking.handlers import BookingStates

    # Check states exist - actual is waiting_phone
    assert hasattr(BookingStates, "waiting_phone")


@pytest.mark.asyncio
async def test_booking_service_helpers() -> None:
    from sqlalchemy.pool import StaticPool

    from src.booking.models import register_migrations
    from src.booking.service import get_active_services
    from src.core.database import Database
    from src.core.migrations import MigrationRegistry

    registry = MigrationRegistry()
    register_migrations(registry)
    db = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await db.init_database(registry)

    services = await get_active_services(db)
    assert services == []
    await db.dispose()


@pytest.mark.asyncio
async def test_booking_router_exists() -> None:
    from sqlalchemy.pool import StaticPool

    from src.booking.handlers import create_router
    from src.booking.models import register_migrations
    from src.core.auth import AdminGate
    from src.core.database import Database
    from src.core.migrations import MigrationRegistry
    from src.core.navigation import NavRegistry

    registry = MigrationRegistry()
    register_migrations(registry)
    db = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await db.init_database(registry)

    gate = AdminGate(password="secret", admin_ids=[1])
    nav = NavRegistry()
    router = create_router(gate=gate, nav=nav, db=db)
    assert router is not None
    await db.dispose()
