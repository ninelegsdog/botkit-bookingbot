"""Coverage boost for bookingbot booking + admin handlers."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Chat, Message, User

from src.admin.handlers import create_router as create_admin_router
from src.booking.handlers import create_router as create_booking_router
from src.core.auth import AdminGate
from src.core.navigation import NavRegistry


def _user(uid: int = 456) -> User:
    return User(id=uid, is_bot=False, first_name="Test User", username="test_user")


def _make_message(uid: int = 456, text: str | None = None) -> Any:
    msg = MagicMock()
    msg.bot = MagicMock()
    msg.chat = Chat(id=1, type="private")
    msg.from_user = _user(uid)
    msg.message_id = 1
    msg.text = text
    msg.answer = AsyncMock()
    msg.edit_text = AsyncMock()
    return msg


def _make_callback(data: str, uid: int = 456) -> Any:
    cq = MagicMock()
    cq.bot = MagicMock()
    cq.data = data
    cq.from_user = _user(uid)
    cq.message = _make_message(uid=uid, text=None)
    cq.answer = AsyncMock()
    return cq


def _find(router: Any, attr: str, name: str) -> Any:
    for h in getattr(router, attr).handlers:
        cb = h.callback
        if hasattr(cb, "__name__") and cb.__name__ == name:
            return cb
    raise AssertionError(f"handler {name!r} not found")


def _unwrap(wrapper: Any) -> Any:
    for cell in wrapper.__closure__ or []:
        if callable(cell.cell_contents):
            return cell.cell_contents
    raise AssertionError("unable to unwrap admin handler")


@pytest.fixture
def gate() -> AdminGate:
    return AdminGate(password="secret", admin_ids=[999])


@pytest.fixture
def nav() -> NavRegistry:
    return NavRegistry()


@pytest.fixture
def db() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fsm() -> FSMContext:
    return FSMContext(
        storage=MemoryStorage(),
        key=StorageKey(bot_id=0, chat_id=123, user_id=456),
    )


@pytest.fixture
def booking_router(gate, nav, db) -> Any:
    return create_booking_router(gate=gate, nav=nav, db=db)


class TestBookingPublicHandlers:

    async def test_start(self, booking_router):
        handler = _find(booking_router, "message", "start")
        msg = _make_message(text="/start")
        await handler(msg)
        msg.answer.assert_awaited_once()
        _, kwargs = msg.answer.await_args
        assert "reply_markup" in kwargs

    async def test_list_services_empty(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "list_services")
        cb = _make_callback("book:services")
        with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=[])):
            await handler(cb)
        cb.answer.assert_awaited_with("Нет доступных услуг.", show_alert=True)

    async def test_list_services_with_services(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "list_services")
        cb = _make_callback("book:services")
        services = [{"id": 1, "name": "Стрижка", "duration_min": 30, "price": 500}]
        with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=services)):
            await handler(cb)
        cb.message.edit_text.assert_awaited_once()
        args, kwargs = cb.message.edit_text.await_args
        assert "Выберите услугу:" in args[0]
        assert "reply_markup" in kwargs

    async def test_select_service_no_dates(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "select_service")
        cb = _make_callback("book:service:1")
        with patch("src.booking.service.get_available_dates", new=AsyncMock(return_value=[])):
            await handler(cb)
        cb.answer.assert_awaited_with("Нет свободных дат.", show_alert=True)

    async def test_select_service_with_dates(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "select_service")
        cb = _make_callback("book:service:1")
        dates = ["2026-09-10", "2026-09-11"]
        with patch("src.booking.service.get_available_dates", new=AsyncMock(return_value=dates)):
            await handler(cb)
        cb.message.edit_text.assert_awaited_once()
        args, kwargs = cb.message.edit_text.await_args
        assert "Выберите дату:" in args[0]
        assert "reply_markup" in kwargs

    async def test_select_date_no_slots(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "select_date")
        cb = _make_callback("book:date:1:2026-09-10")
        with patch("src.booking.service.get_free_slots", new=AsyncMock(return_value=[])):
            await handler(cb)
        cb.answer.assert_awaited_with("Нет свободных слотов.", show_alert=True)

    async def test_select_date_with_slots(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "select_date")
        cb = _make_callback("book:date:1:2026-09-10")
        slots = [{"id": 5, "start_time": "10:00", "end_time": "10:30"}]
        with patch("src.booking.service.get_free_slots", new=AsyncMock(return_value=slots)):
            await handler(cb)
        cb.message.edit_text.assert_awaited_once()
        args, kwargs = cb.message.edit_text.await_args
        assert "Выберите время:" in args[0]
        assert "reply_markup" in kwargs

    async def test_select_slot(self, booking_router, fsm):
        handler = _find(booking_router, "callback_query", "select_slot")
        cb = _make_callback("book:slot:1:5")
        await handler(cb, fsm)
        data = await fsm.get_data()
        assert data["service_id"] == 1
        assert data["slot_id"] == 5
        assert await fsm.get_state() == "BookingStates:waiting_phone"
        cb.message.edit_text.assert_awaited_with("Введите телефон (+71234567890):")

    async def test_capture_phone(self, booking_router, db, fsm):
        await fsm.update_data(service_id=1, slot_id=5)
        handler = _find(booking_router, "message", "capture_phone")
        msg = _make_message(text="+71234567890")
        with patch("src.booking.service.book_slot", new=AsyncMock(return_value=42)):
            await handler(msg, fsm)
        assert await fsm.get_state() is None
        msg.answer.assert_awaited_once()
        args, kwargs = msg.answer.await_args
        assert "✅ Запись #42 подтверждена!" in args[0]
        assert "reply_markup" in kwargs

    async def test_capture_phone_with_payments(self, db, fsm, gate, nav):
        payments = MagicMock()
        payments.create_invoice_link = AsyncMock(return_value="https://pay/42")
        router = create_booking_router(gate=gate, nav=nav, db=db, payments=payments)
        await fsm.update_data(service_id=1, slot_id=5)
        handler = _find(router, "message", "capture_phone")
        msg = _make_message(text="+71234567890")
        with patch("src.booking.service.book_slot", new=AsyncMock(return_value=42)):
            await handler(msg, fsm)
        payments.create_invoice_link.assert_awaited_once()
        msg.answer.assert_awaited_once()
        _, kwargs = msg.answer.await_args
        assert kwargs["reply_markup"] is not None

    async def test_capture_phone_slot_unavailable(self, db, fsm, gate, nav):
        from src.booking.service import SlotUnavailableError

        router = create_booking_router(gate=gate, nav=nav, db=db)
        await fsm.update_data(service_id=1, slot_id=5)
        handler = _find(router, "message", "capture_phone")
        msg = _make_message(text="+71234567890")
        with patch("src.booking.service.book_slot", new=AsyncMock(side_effect=SlotUnavailableError())):
            await handler(msg, fsm)
        assert await fsm.get_state() is None
        msg.answer.assert_awaited_once()
        assert "Слот уже занят" in msg.answer.await_args[0][0]

    async def test_my_bookings_empty(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "my_bookings")
        cb = _make_callback("book:my")
        with patch("src.booking.service.get_user_bookings", new=AsyncMock(return_value=[])):
            await handler(cb)
        cb.message.edit_text.assert_awaited_with("Нет активных записей.")
        cb.answer.assert_awaited_once()

    async def test_my_bookings_with_items(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "my_bookings")
        cb = _make_callback("book:my")
        bookings = [
            {"id": 3, "service_name": "Стрижка", "booking_date": "2026-09-10", "start_time": "10:00", "status": "active"}
        ]
        with patch("src.booking.service.get_user_bookings", new=AsyncMock(return_value=bookings)):
            await handler(cb)
        cb.message.edit_text.assert_awaited_once()
        args, kwargs = cb.message.edit_text.await_args
        assert "#3 Стрижка" in args[0]
        assert "active" in args[0]
        assert "reply_markup" in kwargs

    async def test_cancel_success(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "cancel")
        cb = _make_callback("book:cancel:3")
        with patch("src.booking.service.cancel_booking", new=AsyncMock(return_value=True)):
            await handler(cb)
        cb.answer.assert_awaited_with("Запись отменена.", show_alert=True)

    async def test_cancel_failure(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "cancel")
        cb = _make_callback("book:cancel:3")
        with patch("src.booking.service.cancel_booking", new=AsyncMock(return_value=False)):
            await handler(cb)
        cb.answer.assert_awaited_with("Не удалось отменить.", show_alert=True)

    async def test_delete_my_data(self, booking_router):
        handler = _find(booking_router, "message", "delete_my_data")
        msg = _make_message(text="/delete_my_data")
        await handler(msg)
        msg.answer.assert_awaited_once()
        _, kwargs = msg.answer.await_args
        assert "reply_markup" in kwargs

    async def test_privacy_cancel(self, booking_router):
        handler = _find(booking_router, "callback_query", "privacy_cancel")
        cb = _make_callback("privacy:cancel")
        await handler(cb)
        cb.message.edit_text.assert_awaited_with("Отменено. Данные не тронуты.")
        cb.answer.assert_awaited_once()

    async def test_privacy_confirm(self, booking_router, db):
        handler = _find(booking_router, "callback_query", "privacy_confirm")
        cb = _make_callback("privacy:confirm")
        with patch("src.booking.service.delete_user_data", new=AsyncMock(return_value=3)), \
             patch("src.booking.service.log_audit", new=AsyncMock()) as mock_audit:
            await handler(cb)
            mock_audit.assert_awaited_once_with(db, 456, "delete_my_data")
        cb.message.edit_text.assert_awaited_once()
        args, _ = cb.message.edit_text.await_args
        assert "Удалено записей: 3" in args[0]


class TestAdminHandlers:

    @pytest.fixture
    def admin_router(self, nav, db) -> Any:
        gate = AdminGate(password="secret", admin_ids=[456])
        return create_admin_router(gate=gate, nav=nav, db=db)

    async def test_admin_entry_is_admin(self, admin_router, db, nav):
        gate = AdminGate(password="secret", admin_ids=[456])
        router = create_admin_router(gate=gate, nav=nav, db=db)
        handler = _find(router, "message", "admin_entry")
        msg = _make_message(uid=456, text="/admin")
        await handler(msg, MagicMock())
        msg.answer.assert_awaited_once()
        _, kwargs = msg.answer.await_args
        assert "reply_markup" in kwargs

    async def test_admin_entry_not_admin(self, nav, db, fsm):
        gate = AdminGate(password="secret", admin_ids=[999])
        router = create_admin_router(gate=gate, nav=nav, db=db)
        handler = _find(router, "message", "admin_entry")
        msg = _make_message(uid=456, text="/admin")
        await handler(msg, fsm)
        assert await fsm.get_state() == "AdminStates:waiting_password"
        msg.answer.assert_awaited_with("Введите пароль администратора:")

    async def test_check_password_correct(self, nav, db, fsm):
        gate = AdminGate(password="secret", admin_ids=[999])
        router = create_admin_router(gate=gate, nav=nav, db=db)
        handler = _find(router, "message", "check_password")
        msg = _make_message(uid=456, text="secret")
        await handler(msg, fsm)
        assert await fsm.get_state() is None
        msg.answer.assert_awaited_once()
        _, kwargs = msg.answer.await_args
        assert "reply_markup" in kwargs

    async def test_check_password_incorrect(self, admin_router, fsm):
        handler = _find(admin_router, "message", "check_password")
        msg = _make_message(uid=456, text="wrong")
        await handler(msg, fsm)
        msg.answer.assert_awaited_with("❌ Неверный пароль.")

    async def test_admin_list_services(self, nav, db):
        gate = AdminGate(password="secret", admin_ids=[456])
        router = create_admin_router(gate=gate, nav=nav, db=db)
        wrapper = _find(router, "callback_query", "wrapper")
        list_services = _unwrap(wrapper)
        cb = _make_callback("admin:services", uid=456)
        services = [{"id": 1, "name": "Стрижка", "duration_min": 30, "price": 500}]
        with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=services)):
            await list_services(cb)
        cb.message.edit_text.assert_awaited_once()
        args, _ = cb.message.edit_text.await_args
        assert "Услуги:" in args[0]
        assert "Стрижка" in args[0]

    async def test_admin_list_services_empty(self, nav, db):
        gate = AdminGate(password="secret", admin_ids=[456])
        router = create_admin_router(gate=gate, nav=nav, db=db)
        wrapper = _find(router, "callback_query", "wrapper")
        list_services = _unwrap(wrapper)
        cb = _make_callback("admin:services", uid=456)
        with patch("src.booking.service.get_active_services", new=AsyncMock(return_value=[])):
            await list_services(cb)
        cb.message.edit_text.assert_awaited_with("Пока нет услуг.")