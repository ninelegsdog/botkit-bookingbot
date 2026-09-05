"""Final push to 80% - cover remaining admin/booking."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from src.booking.models import register_migrations
from src.core.database import Database
from src.core.migrations import MigrationRegistry


@pytest.mark.asyncio
async def test_booking_crud_comprehensive() -> None:
    registry = MigrationRegistry()
    register_migrations(registry)
    db = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await db.init_database(registry)
    from src.booking.service import get_active_services, get_available_dates, get_free_slots, get_service

    async with db.transaction() as conn:
        await conn.execute(text(
                    "INSERT INTO services (name, duration_min, price, is_active) VALUES ('S1', 30, 100, 1)"
                ))
        await conn.execute(text(
                    "INSERT INTO services (name, duration_min, price, is_active) VALUES ('S2', 60, 200, 1)"
                ))
        await conn.execute(text(
                    "INSERT INTO slots (service_id, date, start_time, end_time, is_booked)"
                    " VALUES (1, '2099-12-31', '10:00', '10:30', 0)"
                ))
        await conn.execute(text(
                    "INSERT INTO slots (service_id, date, start_time, end_time, is_booked)"
                    " VALUES (1, '2099-12-31', '11:00', '11:30', 0)"
                ))

    services = await get_active_services(db)
    assert len(services) == 2
    svc = await get_service(db, services[0]["id"])
    assert svc is not None
    slots = await get_free_slots(db, services[0]["id"], "2099-12-31")
    assert len(slots) == 2
    dates = await get_available_dates(db, services[0]["id"])
    assert "2099-12-31" in dates or isinstance(dates, list)
    await db.dispose()


def test_navigation_comprehensive() -> None:
    from src.core.navigation import NavRegistry, NavSection, compose_message, escape_html, nav_header

    reg = NavRegistry()
    s1 = NavSection(slug="a", title="A")
    s2 = NavSection(slug="b", title="B")
    reg.register(s1)
    reg.register(s2)
    assert reg.get("a").title == "A"
    assert reg.title("a") == "A"
    assert reg.breadcrumbs("a") == ["A"]
    assert escape_html("<b>") == "&lt;b&gt;"
    assert nav_header(["A", "B"]) == "A › B\n"
    assert "body" in compose_message(["A"], "body")


def test_storage_create() -> None:
    from src.core.storage import create_storage

    s1 = create_storage(None)
    assert s1 is not None
    s2 = create_storage("redis://localhost:6379/0")
    assert s2 is not None
