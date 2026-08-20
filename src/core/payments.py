from collections.abc import Awaitable, Callable
from typing import Protocol

from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery

STARS_CURRENCY = "XTR"


class PaymentProvider(Protocol):
    async def create_invoice_link(
        self, *, title: str, description: str, payload: str, amount: int, currency: str
    ) -> str: ...

    async def verify_payment(self, message: Message) -> bool: ...


class MockPaymentProvider:
    def __init__(self, *, prefix: str = "https://t.me/mock-bot/invoice/") -> None:
        self._prefix = prefix

    async def create_invoice_link(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "XTR"
    ) -> str:
        return f"{self._prefix}{payload}"

    async def verify_payment(self, message: Message) -> bool:
        payment = message.successful_payment
        return bool(payment is not None and payment.total_amount > 0)


class YooKassaPaymentProvider:
    def __init__(self, shop_id: str, secret_key: str) -> None:
        from yookassa import Configuration  # type: ignore[import-untyped]

        Configuration.account_id = shop_id
        Configuration.secret_key = secret_key

    async def create_invoice_link(
        self, *, title: str, description: str, payload: str, amount: int, currency: str = "RUB"
    ) -> str:
        from yookassa import Payment

        payment = Payment.create(
            {
                "amount": {"value": f"{amount}.00", "currency": currency},
                "confirmation": {"type": "redirect", "return_url": "https://t.me/"},
                "capture": True,
                "description": description,
                "metadata": {"payload": payload},
            }
        )
        return str(payment.confirmation.confirmation_url)

    async def verify_payment(self, message: Message) -> bool:
        payment = message.successful_payment
        return bool(payment is not None and payment.total_amount > 0)


def create_payment_provider(name: str, **kwargs: str) -> PaymentProvider:
    if name == "mock":
        return MockPaymentProvider()
    if name == "yookassa":
        return YooKassaPaymentProvider(kwargs["shop_id"], kwargs["secret_key"])
    raise ValueError(f"unknown provider: {name!r}")


def attach_payment_handlers(
    router: Router, provider: PaymentProvider, *, on_confirmed: Callable[[str], Awaitable[None]] | None = None
) -> None:
    @router.pre_checkout_query()
    async def approve_pre_checkout(query: PreCheckoutQuery) -> None:
        await query.answer(ok=True)

    @router.message(F.successful_payment)
    async def confirm_payment(message: Message) -> None:
        payment = message.successful_payment
        if payment is None:
            return
        payload = payment.invoice_payload
        if not await provider.verify_payment(message):
            await message.answer("Оплата не подтверждена.")
            return
        if on_confirmed:
            await on_confirmed(payload)
        await message.answer("Оплата подтверждена.")
