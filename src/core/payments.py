"""Payments shim — re-exports botkit_core.payments."""
from __future__ import annotations

from botkit_core.payments import STARS_CURRENCY as STARS_CURRENCY
from botkit_core.payments import MockPaymentProvider as MockPaymentProvider
from botkit_core.payments import PaymentProvider as PaymentProvider
from botkit_core.payments import YooKassaPaymentProvider as YooKassaPaymentProvider
from botkit_core.payments import attach_payment_handlers as attach_payment_handlers
from botkit_core.payments import create_payment_provider as create_payment_provider

# Демо-провайдер: мок, который сам «подтверждает» платёж. Нужен, чтобы в
# демо-режиме (PAYMENT_PROVIDER=mock) один и тот же путь «создать инвойс →
# successful_payment → on_confirmed» работал без реального Telegram-платежа.
# В проде (yookassa) используется обычный провайдер + webhook.
class DemoPaymentProvider(MockPaymentProvider):
    def __init__(self, *, on_confirmed=None, **kwargs: object) -> None:
        super().__init__(**kwargs)  # type: ignore[arg-type]
        self._on_confirmed = on_confirmed

    def set_on_confirmed(self, callback: object) -> None:
        self._on_confirmed = callback

    async def create_invoice_link(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "XTR"
    ) -> str:
        link = await super().create_invoice_link(
            title=title, description=description, payload=payload, amount=amount, currency=currency
        )
        # В демо платёж «успешен» сразу — вызываем on_confirmed, как будто
        # пришёл successful_payment от Telegram.
        if self._on_confirmed is not None:
            await self._on_confirmed(payload)  # type: ignore[misc]
        return link


__all__ = [
    "DemoPaymentProvider",
    "MockPaymentProvider",
    "PaymentProvider",
    "STARS_CURRENCY",
    "YooKassaPaymentProvider",
    "attach_payment_handlers",
    "create_payment_provider",
]
