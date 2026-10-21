from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Router

from src.core.auth import AdminGate
from src.core.database import Database
from src.core.navigation import NavRegistry

if TYPE_CHECKING:
    from src.core.payments import PaymentProvider


def collect_routers(
    *,
    gate: AdminGate,
    nav: NavRegistry,
    db: Database,
    payments: PaymentProvider | None = None,
    admin_ids: list[int] | None = None,
) -> list[Router]:
    from src.admin.handlers import create_router as admin_router
    from src.booking import service as booking_service
    from src.booking.handlers import create_router as booking_router
    from src.core.payments import MockPaymentProvider, attach_payment_handlers

    provider = payments or MockPaymentProvider()
    booking = booking_router(
        gate=gate, nav=nav, db=db, payments=provider, admin_ids=admin_ids
    )

    async def _on_deposit_confirmed(payload: str) -> None:
        if not payload.startswith("deposit:"):
            return
        try:
            booking_id = int(payload.split(":", 1)[1])
        except ValueError:
            return
        await booking_service.mark_booking_paid(db, booking_id)

    # expected_amount is load-bearing, not optional: core#8 refuses a pre_checkout
    # that declares no expectation, so omitting it here rejected every deposit.
    attach_payment_handlers(
        booking,
        provider,
        on_confirmed=_on_deposit_confirmed,
        expected_amount=booking_service.DEPOSIT_AMOUNT_STARS,
    )

    return [
        booking,
        admin_router(gate=gate, nav=nav, db=db),
    ]
