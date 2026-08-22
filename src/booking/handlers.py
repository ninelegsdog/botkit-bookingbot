from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.auth import AdminGate, mark_admin_router
from src.core.database import Database
from src.core.fsm import text_not_command
from src.core.navigation import NavRegistry, compose_message

from . import service
from .nav import NAV_SECTION


class BookingStates(StatesGroup):
    waiting_phone = State()


def create_router(*, gate: AdminGate, nav: NavRegistry, db: Database, payments: object | None = None) -> Router:
    nav.register(NAV_SECTION)
    public = Router(name="booking")
    admin = mark_admin_router(Router(name="booking_admin"))

    @public.message(Command("start"))
    async def start(message: Message) -> None:
        text = compose_message(
            ["Запись"],
            "Выберите действие:",
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📅 Записаться", callback_data="book:services")],
                [InlineKeyboardButton(text="🗓 Мои записи", callback_data="book:my")],
            ]
        )
        await message.answer(text, reply_markup=kb)

    @public.callback_query(F.data == "book:services")
    async def list_services(callback: CallbackQuery) -> None:
        services = await service.get_active_services(db)
        if not services:
            await callback.answer("Нет доступных услуг.", show_alert=True)
            return
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"{s['name']} — {s['duration_min']} мин, {s['price']}₽",
                    callback_data=f"book:service:{s['id']}",
                )
            ]
            for s in services
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text("Выберите услугу:", reply_markup=kb)  # type: ignore
        await callback.answer()

    @public.callback_query(F.data.startswith("book:service:"))
    async def select_service(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        service_id = int(callback.data.split(":")[2])
        dates = await service.get_available_dates(db, service_id)
        if not dates:
            await callback.answer("Нет свободных дат.", show_alert=True)
            return
        buttons = [[InlineKeyboardButton(text=d, callback_data=f"book:date:{service_id}:{d}")] for d in dates[:10]]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text("Выберите дату:", reply_markup=kb)  # type: ignore
        await callback.answer()

    @public.callback_query(F.data.startswith("book:date:"))
    async def select_date(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        parts = callback.data.split(":")
        service_id = int(parts[2])
        date_str = parts[3]
        slots = await service.get_free_slots(db, service_id, date_str)
        if not slots:
            await callback.answer("Нет свободных слотов.", show_alert=True)
            return
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"{s['start_time']} — {s['end_time']}",
                    callback_data=f"book:slot:{service_id}:{s['id']}",
                )
            ]
            for s in slots
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text("Выберите время:", reply_markup=kb)  # type: ignore
        await callback.answer()

    @public.callback_query(F.data.startswith("book:slot:"))
    async def select_slot(callback: CallbackQuery, state: FSMContext) -> None:
        if not callback.data:
            return
        parts = callback.data.split(":")
        await state.update_data(service_id=int(parts[2]), slot_id=int(parts[3]))
        await state.set_state(BookingStates.waiting_phone)
        await callback.message.edit_text("Введите телефон (+71234567890):")  # type: ignore
        await callback.answer()

    @public.message(BookingStates.waiting_phone, text_not_command)
    async def capture_phone(message: Message, state: FSMContext) -> None:
        phone = message.text or ""
        data = await state.get_data()
        try:
            booking_id = await service.book_slot(
                db,
                service_id=data["service_id"],
                slot_id=data["slot_id"],
                user_id=message.from_user.id,  # type: ignore
                name=message.from_user.first_name or "",  # type: ignore
                phone=phone,
            )
            await state.clear()
            deposit_kb: InlineKeyboardMarkup | None = _main_menu()
            if payments is not None:
                link = await payments.create_invoice_link(  # type: ignore[attr-defined]
                    title="Депозит",
                    description=f"Депозит по записи #{booking_id}",
                    payload=f"deposit:{booking_id}",
                    amount=500,
                    currency="XTR",
                )
                deposit_kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="💳 Внести депозит", url=link)],
                        *_main_menu().inline_keyboard,
                    ]
                )
            await message.answer(
                compose_message(["Запись"], f"✅ Запись #{booking_id} подтверждена!"),
                reply_markup=deposit_kb,
            )
        except service.SlotUnavailableError:
            await state.clear()
            await message.answer("❌ Слот уже занят. Выберите другой.", reply_markup=_main_menu())

    @public.callback_query(F.data == "book:my")
    async def my_bookings(callback: CallbackQuery) -> None:
        bookings = await service.get_user_bookings(db, callback.from_user.id)
        if not bookings:
            await callback.message.edit_text("Нет активных записей.")  # type: ignore
            await callback.answer()
            return
        text = "\n".join(
            f"#{b['id']} {b['service_name']} — {b['booking_date']} {b['start_time']} ({b['status']})" for b in bookings
        )
        buttons = [
            [InlineKeyboardButton(text=f"❌ Отменить #{b['id']}", callback_data=f"book:cancel:{b['id']}")]
            for b in bookings
        ]
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await callback.message.edit_text(text, reply_markup=kb)  # type: ignore
        await callback.answer()

    @public.callback_query(F.data.startswith("book:cancel:"))
    async def cancel(callback: CallbackQuery) -> None:
        if not callback.data:
            return
        booking_id = int(callback.data.split(":")[2])
        ok = await service.cancel_booking(db, booking_id, callback.from_user.id)
        if ok:
            await callback.answer("Запись отменена.", show_alert=True)
        else:
            await callback.answer("Не удалось отменить.", show_alert=True)

    @public.message(Command("delete_my_data"))
    async def delete_my_data(message: Message) -> None:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Да, удалить", callback_data="privacy:confirm"),
                    InlineKeyboardButton(text="❌ Отмена", callback_data="privacy:cancel"),
                ]
            ]
        )
        await message.answer(
            "⚠️ Это удалит все ваши записи, напоминания и отзывы. Действие необратимо.",
            reply_markup=kb,
        )

    @public.callback_query(F.data == "privacy:cancel")
    async def privacy_cancel(callback: CallbackQuery) -> None:
        if callback.message:
            await callback.message.edit_text("Отменено. Данные не тронуты.")  # type: ignore[union-attr]
        await callback.answer()

    @public.callback_query(F.data == "privacy:confirm")
    async def privacy_confirm(callback: CallbackQuery) -> None:
        uid = callback.from_user.id
        deleted = await service.delete_user_data(db, uid)
        await service.log_audit(db, uid, "delete_my_data")
        if callback.message:
            await callback.message.edit_text(f"Удалено записей: {deleted}. Ваши данные стёрты.")  # type: ignore[union-attr]
        await callback.answer()

    public.include_router(admin)
    return public


def _main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📅 Записаться", callback_data="book:services")],
            [InlineKeyboardButton(text="🗓 Мои записи", callback_data="book:my")],
        ]
    )
