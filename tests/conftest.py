"""Shared fixtures and fake session for dispatcher-level e2e tests + testcontainers."""

from __future__ import annotations

import datetime
import json
import os
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from src.app import collect_routers
from src.booking.models import register_migrations
from src.core.auth import AdminGate
from src.core.bot_factory import build_dispatcher
from src.core.database import Database
from src.core.migrations import MigrationRegistry
from src.core.navigation import NavRegistry


@pytest.fixture(scope="session")
def postgres_container() -> Any:
    """PostgreSQL 16 container for integration tests."""
    from testcontainers.community.postgres import PostgresContainer
    container = PostgresContainer("postgres:16-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture(scope="session")
def redis_container() -> Any:
    """Redis 7 container for integration tests."""
    from testcontainers.community.redis import RedisContainer
    container = RedisContainer("redis:7-alpine")
    container.start()
    yield container
    container.stop()


@pytest.fixture
def postgres_url(postgres_container) -> str:
    """Get PostgreSQL connection URL."""
    return postgres_container.get_connection_url().replace("postgresql+psycopg2", "postgresql+asyncpg")


@pytest.fixture
def redis_url(redis_container) -> str:
    """Get Redis connection URL."""
    return f"redis://{redis_container.get_container_host_ip()}:{redis_container.get_exposed_port(6379)}"


@pytest.fixture
async def db_engine(postgres_url: str):
    """Create async SQLAlchemy engine."""
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(postgres_url, echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def db_session(db_engine) -> Any:
    """Create database session for tests."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
    async_session = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        yield session


@pytest.fixture
async def redis_client(redis_url: str):
    """Create Redis client for tests."""
    import redis.asyncio as redis
    client = redis.from_url(redis_url, decode_responses=True)
    yield client
    await client.aclose()


class FakeSession:
    """Records API calls, returns minimal valid responses."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    async def close(self) -> None:
        pass

    async def make_request(
        self,
        bot: Any,
        method: Any,
        timeout: int | None = None,
    ) -> Any:
        self.calls.append(type(method).__name__)
        return True

    async def stream_content(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,
        chunk_size: int = 65536,
    ) -> Any:
        yield b""


@pytest.fixture
async def env():
    """Fake session environment for unit tests."""
    from src.app import collect_routers
    from src.booking.models import register_migrations
    from src.core.auth import AdminGate
    from src.core.bot_factory import build_dispatcher
    from src.core.database import Database
    from src.core.migrations import MigrationRegistry
    from src.core.navigation import NavRegistry
    from aiogram import Bot, Dispatcher
    from aiogram.fsm.storage.memory import MemoryStorage
    from src.core.auth import AdminGate
    from src.core.navigation import NavRegistry

    registry = MigrationRegistry()
    register_migrations(registry)
    database = Database("sqlite+aiosqlite://")
    await database.init()

    dp = build_dispatcher(
        routers=collect_routers(gate=AdminGate("pw"), nav=NavRegistry(), db=database),
        storage=MemoryStorage(),
    )
    bot = Bot(token="42:TEST_TOKEN")
    yield database, dp, bot
    await bot.session.close()
    await database.dispose()


async def _seed_service_and_slot(db) -> tuple[int, int]:
    from sqlalchemy import text
    async with db.transaction() as conn:
        await conn.execute(text("INSERT INTO services (name) VALUES (Haircut)"))
        row = await conn.execute(text("SELECT id FROM services LIMIT 1"))
        service_id = int(row.scalar_one())
        await conn.execute(
            text(
                "INSERT INTO slots (service_id, date, start_time, end_time) "
                "VALUES (:sid, 2030-01-01, 10:00, 11:00)"
            ),
            {"sid": service_id},
        )
        row = await conn.execute(text("SELECT id FROM slots LIMIT 1"))
        slot_id = row.scalar_one()
    return int(service_id), int(slot_id)


def _user(uid: int):
    from aiogram.types import User
    return User(id=uid, first_name="Test", is_bot=False)


def _chat(uid: int):
    from aiogram.types import Chat
    return Chat(id=uid, type="private")


def _msg_update(update_id: int, uid: int, text_value: str):
    import datetime
    from aiogram.types import Update, Message, Chat, User
    return Update(
        update_id=update_id,
        message=Message(
            message_id=update_id,
            date=datetime.datetime.now(tz=datetime.UTC),
            chat=_chat(uid),
            from_user=_user(uid),
            text=text_value,
        ),
    )


def _cb_update(update_id: int, uid: int, data: str):
    from aiogram.types import Update, CallbackQuery, Message, Chat, User
    msg = Message(
        message_id=update_id,
        date=datetime.datetime.now(tz=datetime.UTC),
        chat=_chat(uid),
        from_user=_user(uid),
    )
    return Update(
        update_id=update_id,
        callback_query=CallbackQuery(
            id=f"c{update_id}",
            from_user=_user(uid),
            chat_instance="ci",
            data=data,
            message=msg,
        ),
    )


def _fsm(dp, bot, uid: int):
    from aiogram.fsm.context import FSMContext
    from aiogram.fsm.storage.base import StorageKey
    key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
    return FSMContext(storage=dp.storage, key=key)


_PAYLOADS_DIR = Path(__file__).parent / "fixtures" / "payloads"


@pytest.fixture
def load_payload() -> Any:
    """Load a JSON Telegram-update fixture from tests/fixtures/payloads/."""

    def _load(name: str) -> dict[str, Any]:
        return json.loads((_PAYLOADS_DIR / name).read_text(encoding="utf-8"))  # type: ignore[no-any-return]

    return _load


def pytest_collection_modifyitems(config: Any, items: Any) -> None:
    """Tag offline tests as no_req; skip real Telegram (req) tests without RUN_TELEGRAM_E2E=1."""
    for item in items:
        if "integration" in item.keywords:
            continue
        if "req" in item.keywords:
            if os.getenv("RUN_TELEGRAM_E2E") != "1":
                item.add_marker(
                    pytest.mark.skip(reason="set RUN_TELEGRAM_E2E=1 to run real Telegram tests")
                )
        elif "no_req" not in item.keywords:
            item.add_marker(pytest.mark.no_req)

def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="run integration tests with testcontainers",
    )
