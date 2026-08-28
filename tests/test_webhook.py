"""Webhook endpoint tests (in-process aiohttp + black-box style via test client)."""
from __future__ import annotations

from typing import Any

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiohttp.test_utils import TestClient, TestServer

from src.core.webhook import build_webhook_app

SECRET = "local-test-secret"


class _NullSession(BaseSession):
    async def close(self) -> None: ...

    async def make_request(self, bot: Bot, method: Any, request_timeout: int | None = None) -> Any:
        return True

    async def stream_content(self, *args, **kwargs):  # noqa: ANN002, ANN003
        yield b""


@pytest.fixture
async def webhook_client() -> Any:
    dp = Dispatcher()
    bot = Bot(token="42:TEST", session=_NullSession())
    app = build_webhook_app(dp, bot, secret_token=SECRET)
    server = TestServer(app)
    client = TestClient(server)
    await client.start_server()
    yield client
    await client.close()
    await bot.session.close()


_VALID_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1,
        "chat": {"id": 1, "type": "private"},
        "from": {"id": 1, "is_bot": False, "first_name": "T"},
        "text": "hi",
    },
}


@pytest.mark.no_req
@pytest.mark.webhook
async def test_webhook_accepts_valid_secret(webhook_client: TestClient) -> None:
    resp = await webhook_client.post(
        "/webhook",
        json=_VALID_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": SECRET},
    )
    assert resp.status in (200, 202)


@pytest.mark.no_req
@pytest.mark.webhook
async def test_webhook_rejects_wrong_secret(webhook_client: TestClient) -> None:
    resp = await webhook_client.post(
        "/webhook",
        json=_VALID_UPDATE,
        headers={"X-Telegram-Bot-Api-Secret-Token": "wrong"},
    )
    assert resp.status in (401, 403)


@pytest.mark.no_req
@pytest.mark.webhook
async def test_webhook_rejects_bad_json(webhook_client: TestClient) -> None:
    resp = await webhook_client.post(
        "/webhook",
        data=b"not-json",
        headers={
            "X-Telegram-Bot-Api-Secret-Token": SECRET,
            "Content-Type": "application/json",
        },
    )
    assert resp.status in (400, 415, 500)
