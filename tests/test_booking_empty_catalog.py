"""F5: пустой каталог услуг — оператор обязан узнать, а не молчать.

Факт плана bot-fixes F5: без services/weekly_schedule/slots клиент получает
«Нет доступных услуг.», бот сам данные не создаёт и владелец не узнаёт
ничего — исходная находка всего проекта. Слабость эксплуатационная: тишина
со стороны бота неотличима от «всё хорошо».

Правка: при пустом каталоге клиенту по-прежнему вежливый отказ, а владельцу
(admin_ids) уходит уведомление с chat id и подсказкой, что делать.

Негативный контроль (план: «убрать отправку — падает»): вернуть молчание —
тесты падают по `send_message.assert_awaited*`.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.types import Chat, User

from src.booking.handlers import create_router as create_booking_router
from src.core.auth import AdminGate
from src.core.navigation import NavRegistry


def _user(uid: int = 456) -> User:
    return User(id=uid, is_bot=False, first_name="Test User", username="test_user")


def _make_callback(data: str, uid: int = 456) -> Any:
    cq = MagicMock()
    cq.bot = MagicMock()
    cq.bot.send_message = AsyncMock()
    cq.data = data
    cq.from_user = _user(uid)
    cq.message = MagicMock()
    cq.message.chat = Chat(id=1, type="private")
    cq.message.edit_text = AsyncMock()
    cq.answer = AsyncMock()
    return cq


def _find(router: Any, attr: str, name: str) -> Any:
    for h in getattr(router, attr).handlers:
        cb = h.callback
        if hasattr(cb, "__name__") and cb.__name__ == name:
            return cb
    raise AssertionError(f"handler {name!r} not found")


ADMIN_ID = 999


@pytest.fixture
def nav() -> NavRegistry:
    return NavRegistry()


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def router(nav, db) -> Any:
    gate = AdminGate(password="secret", admin_ids=[ADMIN_ID])
    return create_booking_router(gate=gate, nav=nav, db=db, admin_ids=[ADMIN_ID])


async def test_empty_catalog_notifies_owner(router) -> None:
    """Пустой каталог: клиент видит отказ, владелец — уведомление."""
    handler = _find(router, "callback_query", "list_services")
    cb = _make_callback("book:services")
    with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=[])):
        await handler(cb)
    cb.answer.assert_awaited_with("Нет доступных услуг.", show_alert=True)
    cb.bot.send_message.assert_awaited_once()
    chat_id, text = cb.bot.send_message.await_args.args[:2]
    assert chat_id == ADMIN_ID
    assert "услуг" in text.lower()
    assert "пуст" in text.lower()


async def test_notification_carries_client_and_hint(router) -> None:
    """В уведомлении есть, кого не пустили, и что делать."""
    handler = _find(router, "callback_query", "list_services")
    cb = _make_callback("book:services", uid=456)
    with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=[])):
        await handler(cb)
    text = cb.bot.send_message.await_args.args[1]
    assert "456" in text or "book:services" in text or "/admin" in text


async def test_notification_not_sent_when_catalog_filled(router) -> None:
    """Активный каталог: уведомления нет — иначе владелец получит шум."""
    handler = _find(router, "callback_query", "list_services")
    cb = _make_callback("book:services")
    services = [{"id": 1, "name": "Стрижка", "duration_min": 30, "price": 500}]
    with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=services)):
        await handler(cb)
    cb.bot.send_message.assert_not_awaited()


async def test_notification_is_storm_guarded(router) -> None:
    """Второй клиент подряд не порождает второе уведомление сразу."""
    handler = _find(router, "callback_query", "list_services")
    with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=[])):
        first = _make_callback("book:services", uid=1)
        await handler(first)
        second = _make_callback("book:services", uid=2)
        await handler(second)
    assert first.bot.send_message.await_count == 1
    assert second.bot.send_message.await_count == 0


async def test_notification_failure_does_not_break_client_answer(router) -> None:
    """Владелец недоступен (бот заблокирован) — клиент всё равно получает ответ."""
    handler = _find(router, "callback_query", "list_services")
    cb = _make_callback("book:services")
    cb.bot.send_message = AsyncMock(side_effect=RuntimeError("bot was blocked by the user"))
    with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=[])):
        await handler(cb)
    cb.answer.assert_awaited_with("Нет доступных услуг.", show_alert=True)
