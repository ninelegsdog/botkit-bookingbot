from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from src.core.auth import AdminGate, mark_admin_router, require_admin
from src.core.database import Database
from src.core.fsm import text_not_command


class AdminStates(StatesGroup):
    waiting_password = State()
    waiting_service_name = State()
    waiting_service_price = State()


ADMIN_MENU_TEXT = "🔐 Админ-панель"


def create_router(*, gate: AdminGate, nav: object, db: Database) -> Router:
    admin = mark_admin_router(Router(name="admin"))

    @admin.message(Command("admin"))
    async def admin_entry(message: Message, state: FSMContext) -> None:
        uid = message.from_user.id  # type: ignore
        if gate.is_admin(uid):
            await _show_admin_menu(message)
            return
        await state.set_state(AdminStates.waiting_password)
        await message.answer("Введите пароль администратора:")

    @admin.message(AdminStates.waiting_password, text_not_command)
    async def check_password(message: Message, state: FSMContext) -> None:
        uid = message.from_user.id  # type: ignore
        if gate.authorize(uid, message.text or ""):
            await state.clear()
            await _show_admin_menu(message)
        else:
            await message.answer("❌ Неверный пароль.")

    async def _show_admin_menu(message: Message) -> None:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Услуги", callback_data="admin:services")],
                [InlineKeyboardButton(text="📅 Расписание", callback_data="admin:schedule")],
                [InlineKeyboardButton(text="🗓 Записи", callback_data="admin:bookings")],
            ]
        )
        await message.answer(ADMIN_MENU_TEXT, reply_markup=kb)

    @admin.callback_query(F.data == "admin:services")
    @require_admin(gate)
    async def list_services(callback: CallbackQuery) -> None:
        from src.booking.service import get_active_services

        services = await get_active_services(db)
        if services:
            text = "Услуги:\n" + "\n".join(
                f"• {s['name']} — {s['duration_min']} мин, {s['price']}₽" for s in services
            )
        else:
            text = "Пока нет услуг."
        await callback.message.edit_text(text)  # type: ignore
        await callback.answer()

    return admin
