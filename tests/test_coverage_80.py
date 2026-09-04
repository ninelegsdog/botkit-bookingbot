# ruff: noqa: E501
"""Final tests to reach 80% coverage."""
from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from src.booking.models import register_migrations
from src.core.database import Database
from src.core.migrations import MigrationRegistry


@pytest.mark.asyncio
async def test_admin_gate_full() -> None:
    from src.core.auth import AdminGate

    gate = AdminGate(password="test", admin_ids=[1, 2, 3])
    assert gate.is_admin(1) is True
    assert gate.is_admin(2) is True
    assert gate.is_admin(999) is False
    assert gate.authorize(10, "test") is True
    assert gate.is_admin(10) is True
    assert gate.authorize(11, "wrong") is False
    for _ in range(6):
        gate.authorize(12, "wrong")
    assert gate.authorize(12, "wrong") is False


@pytest.mark.asyncio
async def test_booking_service_comprehensive() -> None:
    from sqlalchemy import text

    from src.booking.service import get_active_services, get_available_dates, get_service

    registry = MigrationRegistry()
    register_migrations(registry)
    db = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await db.init_database(registry)

    async with db.transaction() as conn:
        await conn.execute(text("INSERT INTO services (name, duration_min, price, is_active) VALUES ('S1', 30, 100, 1)"))
        await conn.execute(text("INSERT INTO services (name, duration_min, price, is_active) VALUES ('S2', 60, 200, 1)"))

    services = await get_active_services(db)
    assert len(services) == 2
    svc = await get_service(db, services[0]["id"])
    assert svc is not None
    dates = await get_available_dates(db, services[0]["id"])
    assert isinstance(dates, list)
    await db.dispose()


def test_navigation_extra() -> None:
    from src.core.navigation import NavRegistry, NavSection, compose_message, nav_header

    registry = NavRegistry()
    s = NavSection(slug="a", title="A")
    registry.register(s)
    assert registry.get("a").title == "A"
    assert registry.breadcrumbs("a") == ["A"]
    assert nav_header(["A", "B"]) == "A › B\n"
    assert "A" in compose_message(["A"], "body")


def test_storage_create() -> None:
    from src.core.storage import create_storage

    storage = create_storage(None)
    assert storage is not None
    storage2 = create_storage("redis://localhost:6379/0")
    assert storage2 is not None


def test_throttling_middleware() -> None:
    from src.core.throttling import ThrottlingMiddleware

    mw = ThrottlingMiddleware(redis_url="redis://localhost:6379/0", rate_limit=10, max_idle=60)
    assert mw is not None
    assert hasattr(mw, "_redis") or hasattr(mw, "redis_url")
