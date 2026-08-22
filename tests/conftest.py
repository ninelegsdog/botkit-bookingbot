"""Shared fixtures and fake session for dispatcher-level e2e tests."""

from __future__ import annotations

import datetime
from collections.abc import AsyncIterator
from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import base as base_method
from aiogram.types import CallbackQuery, Chat, Message, Update, User
from sqlalchemy import text
from sqlalchemy.pool import StaticPool

from src.app import collect_routers
from src.booking.models import register_migrations
from src.core.auth import AdminGate
from src.core.bot_factory import build_dispatcher
from src.core.database import Database
from src.core.migrations import MigrationRegistry
from src.core.navigation import NavRegistry


class FakeSession(BaseSession):
    """Records API calls, returns minimal valid responses."""

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []

    async def close(self) -> None:
        pass

    async def make_request(
        self,
        bot: Bot,
        method: base_method.TelegramMethod[Any],
        timeout: int | None = None,  # noqa: ASYNC109
    ) -> Any:
        self.calls.append(type(method).__name__)
        return True

    async def stream_content(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: int = 30,  # noqa: ASYNC109
        chunk_size: int = 65536,
    ) -> AsyncIterator[bytes]:
        yield b""


@pytest.fixture
async def env() -> AsyncIterator[tuple[Database, Dispatcher, Bot, FakeSession]]:
    registry = MigrationRegistry()
    register_migrations(registry)
    database = Database("sqlite+aiosqlite://", poolclass=StaticPool)
    await database.init_database(registry)

    dp = build_dispatcher(
        routers=collect_routers(gate=AdminGate("pw"), nav=NavRegistry(), db=database),
        storage=MemoryStorage(),
    )
    session = FakeSession()
    bot = Bot(token="42:TEST_TOKEN", session=session)
    yield database, dp, bot, session
    await bot.session.close()
    await database.dispose()


async def _seed_service_and_slot(db: Database) -> tuple[int, int]:
    async with db.transaction() as conn:
        await conn.execute(text("INSERT INTO services (name) VALUES ('Haircut')"))
        row = await conn.execute(text("SELECT id FROM services LIMIT 1"))
        service_id = int(row.scalar_one())
        await conn.execute(
            text(
                "INSERT INTO slots (service_id, date, start_time, end_time) "
                "VALUES (:sid, '2030-01-01', '10:00', '11:00')"
            ),
            {"sid": service_id},
        )
        row = await conn.execute(text("SELECT id FROM slots LIMIT 1"))
        slot_id = row.scalar_one()
    return int(service_id), int(slot_id)


def _user(uid: int) -> User:
    return User(id=uid, first_name="Test", is_bot=False)


def _chat(uid: int) -> Chat:
    return Chat(id=uid, type="private")


def _msg_update(update_id: int, uid: int, text_value: str) -> Update:
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


def _cb_update(update_id: int, uid: int, data: str) -> Update:
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


def _fsm(dp: Dispatcher, bot: Bot, uid: int) -> FSMContext:
    key = StorageKey(bot_id=bot.id, chat_id=uid, user_id=uid)
    return FSMContext(storage=dp.storage, key=key)
