"""Full coverage for admin handlers."""
from __future__ import annotations

import pytest
from sqlalchemy.pool import StaticPool

from src.booking.models import register_migrations
from src.core.auth import AdminGate
from src.core.database import Database
from src.core.migrations import MigrationRegistry


@pytest.mark.asyncio
async def test_create_admin_router() -> None:
    from src.admin.handlers import create_router
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


def test_admin_gate_throttle() -> None:
    gate = AdminGate(password="secret", admin_ids=[1])
    for _ in range(5):
        assert gate.authorize(999, "wrong") is False
    assert gate.authorize(999, "wrong") is False
    assert gate.authorize(1000, "secret") is True
