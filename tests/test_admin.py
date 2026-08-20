import pytest
from sqlalchemy.pool import StaticPool

from src.booking.models import register_migrations
from src.core.auth import AdminGate
from src.core.database import Database
from src.core.migrations import MigrationRegistry


@pytest.fixture
async def db():
    registry = MigrationRegistry()
    register_migrations(registry)
    database = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await database.init_database(registry)
    yield database
    await database.dispose()


def test_admin_gate_unauthorized():
    gate = AdminGate("secret")
    assert gate.is_admin(123) is False


def test_admin_gate_authorize():
    gate = AdminGate("secret")
    assert gate.authorize(123, "secret") is True
    assert gate.is_admin(123) is True


def test_admin_gate_wrong_password():
    gate = AdminGate("secret")
    assert gate.authorize(123, "wrong") is False
    assert gate.is_admin(123) is False
