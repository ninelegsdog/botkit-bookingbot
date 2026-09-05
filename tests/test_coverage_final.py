"""Final tests to reach 80% - comprehensive."""
from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from src.booking.models import register_migrations
from src.core.database import Database
from src.core.migrations import MigrationRegistry


@pytest.mark.asyncio
async def test_booking_admin_comprehensive() -> None:
    from src.core.auth import AdminGate
    from src.core.navigation import NavRegistry, NavSection

    gate = AdminGate(password="secret", admin_ids=[1, 2])
    assert gate.is_admin(1) is True
    assert gate.authorize(3, "secret") is True
    assert gate.is_admin(3) is True

    reg = NavRegistry()
    s = NavSection(slug="test", title="Test")
    reg.register(s)
    assert reg.get("test") is not None
    assert reg.title("test") == "Test"
    assert reg.breadcrumbs("test") == ["Test"]


@pytest.mark.asyncio
async def test_booking_service_full() -> None:
    from src.booking.service import get_active_services, get_service

    registry = MigrationRegistry()
    register_migrations(registry)
    db = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await db.init_database(registry)

    async with db.transaction() as conn:
        await conn.execute(text("INSERT INTO services (name, duration_min, price, is_active) VALUES ('A', 30, 100, 1)"))
        await conn.execute(text("INSERT INTO services (name, duration_min, price, is_active) VALUES ('B', 60, 200, 0)"))

    services = await get_active_services(db)
    assert len(services) == 1
    assert services[0]["name"] == "A"
    svc = await get_service(db, services[0]["id"])
    assert svc["name"] == "A"
    svc_none = await get_service(db, 9999)
    assert svc_none is None
    await db.dispose()


def test_navigation_comprehensive() -> None:
    from src.core.navigation import NavRegistry, NavSection, compose_message, escape_html

    reg = NavRegistry()
    s1 = NavSection(slug="x", title="X")
    s2 = NavSection(slug="y", title="Y")
    reg.register(s1)
    reg.register(s2)
    assert reg.get("x").title == "X"
    assert escape_html("<a>") == "&lt;a&gt;"
    assert "X" in compose_message(["X"], "body")


def test_storage_throttling() -> None:
    from src.core.storage import create_storage
    from src.core.throttling import ThrottlingMiddleware

    s1 = create_storage(None)
    assert s1 is not None
    s2 = create_storage("redis://localhost:6379/0")
    assert s2 is not None
    mw = ThrottlingMiddleware(redis_url="redis://localhost:6379/0", rate_limit=5, max_idle=30)
    assert mw is not None
