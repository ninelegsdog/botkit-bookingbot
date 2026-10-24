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
    from src.core.payments import MockPaymentProvider, attach_payment_handlers, create_payment_provider

    async def _on_deposit_confirmed(payload: str, *, user_id: int | None = None) -> None:
        if not payload.startswith("deposit:"):
            return
        try:
            booking_id = int(payload.split(":", 1)[1])
        except ValueError:
            return
        await booking_service.mark_booking_paid(db, booking_id)

    import os

    if payments is None:
        provider_name = os.getenv("PAYMENT_PROVIDER", "mock").strip().lower() or "mock"
        if provider_name == "yookassa":
            provider = create_payment_provider(
                "yookassa",
                shop_id=os.getenv("YOOKASSA_SHOP_ID", ""),
                secret_key=os.getenv("YOOKASSA_SECRET_KEY", ""),
            )
        else:
            provider = create_payment_provider(
                "mock", on_confirmed=_on_deposit_confirmed, auto_confirm=True
            )
    else:
        provider = payments

    booking = booking_router(
        gate=gate, nav=nav, db=db, payments=provider, admin_ids=admin_ids
    )

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
