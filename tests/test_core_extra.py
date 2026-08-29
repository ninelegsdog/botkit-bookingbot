from __future__ import annotations

import asyncio
import contextlib
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core import storage, throttling, ui, webhook
from src.core.config import Settings, parse_admin_ids
from src.core.sentry import init_sentry


def test_parse_admin_ids() -> None:
    assert parse_admin_ids("") == []
    assert parse_admin_ids("1,2,3") == [1, 2, 3]
    assert parse_admin_ids(" 7 , 8 ") == [7, 8]


def test_settings_valid(monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123456789:AAfake")
    monkeypatch.setenv("ADMIN_PASSWORD", "secret")
    monkeypatch.setenv("ADMIN_IDS", "[1,2]")
    s = Settings(_env_file=None)
    assert s.bot_token == "123456789:AAfake"
    assert s.admin_ids == [1, 2]
    assert s.metrics_port == 8080


def test_settings_missing_required(monkeypatch) -> None:
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    monkeypatch.delenv("ADMIN_PASSWORD", raising=False)
    monkeypatch.delenv("ADMIN_IDS", raising=False)
    with pytest.raises(RuntimeError):
        Settings(_env_file=None)


def test_create_storage_memory() -> None:
    assert isinstance(storage.create_storage(None), storage.MemoryStorage)


def test_create_storage_redis() -> None:
    fake_redis = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "redis": MagicMock(),
            "redis.asyncio": MagicMock(from_url=lambda *a, **k: fake_redis),
            "aiogram.fsm.storage.redis": MagicMock(RedisStorage=MagicMock),
        },
    ):
        result = storage.create_storage("redis://x")
    assert isinstance(result, MagicMock)


def test_empty_keyboard() -> None:
    kb = ui.empty_keyboard()
    assert kb.inline_keyboard == []


def test_build_webhook_app() -> None:
    app = webhook.build_webhook_app(MagicMock(), MagicMock(), "secret")
    paths = [str(r.resource.canonical) for r in app.router.routes() if r.resource]
    assert "/webhook" in paths


def test_init_sentry_disabled() -> None:
    init_sentry(None)


def test_init_sentry_no_sdk(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "sentry_sdk", None)
    init_sentry("https://x@sentry.io/1")


class _FakeRedis:
    def __init__(self) -> None:
        self.get = AsyncMock(return_value=None)
        self.set = AsyncMock()


@pytest.fixture
def throttler():
    with patch.object(throttling.redis, "from_url", return_value=_FakeRedis()):
        yield throttling.ThrottlingMiddleware("redis://x")


async def test_throttle_passes_without_user(throttler) -> None:
    event = MagicMock()
    event.from_user = None
    handler = AsyncMock(return_value="ok")
    assert await throttler(handler, event, {}) == "ok"
    assert handler.await_count == 1


async def test_throttle_allows_then_blocks(throttler) -> None:
    user = SimpleNamespace(id=5)
    event = MagicMock()
    event.from_user = user
    handler = AsyncMock(return_value="ok")
    assert await throttler(handler, event, {}) == "ok"
    assert handler.await_count == 1
    throttler._redis.get.return_value = str(time.time())
    assert await throttler(handler, event, {}) is None
    assert handler.await_count == 1


async def test_scheduler_loop_sends() -> None:
    from src.reminder import service

    with patch.object(
        service,
        "get_due_reminders",
        new=AsyncMock(return_value=[{"user_id": "1", "text": "t", "id": 1}]),
    ), patch.object(service, "mark_sent", new=AsyncMock()) as mark:
        bot = MagicMock()
        bot.send_message = AsyncMock()
        db = MagicMock()
        task = asyncio.create_task(_run_scheduler(db, bot))
        await asyncio.sleep(0.05)
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
    assert bot.send_message.await_count >= 1
    assert mark.await_count >= 1


async def _run_scheduler(db, bot) -> None:
    from src.reminder.scheduler import scheduler_loop

    await scheduler_loop(db, bot, interval=1)
