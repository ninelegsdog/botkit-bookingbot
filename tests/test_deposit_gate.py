"""The deposit gate must approve a real charge and refuse everything else.

This exists because the gate shipped broken. Bumping botkit-core to v0.8.4 pulled in core#8,
which made `pre_checkout` refuse when the caller declares no expected payload and no expected
amount. bookingbot declared neither, so every deposit was answered "Покупка не настроена"
and Telegram rejected the charge - for about 45 minutes, until the container was rolled back.

CI stayed green throughout: bookingbot had no pre_checkout test at all. The path was simply
not covered, which is how an undeclared gate and a wrong gate look identical.

The tests below go through `collect_routers`, the function production uses, so they exercise
the real attach call rather than a re-created one. That matters: a test which attaches its own
handlers proves only that core works, which was never in doubt. The failure was in what
production passes to it.
"""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from aiogram import Router

from src.app import collect_routers
from src.booking import service
from src.core.auth import AdminGate
from src.core.database import Database
from src.core.navigation import NavRegistry
from src.core.payments import MockPaymentProvider, attach_payment_handlers

ROOT = Path(__file__).resolve().parents[1]


def _production_routers() -> list[Any]:
    """Routers built exactly the way src/app.py builds them.

    The database is constructed but never initialised: `collect_routers` only stores it for
    the handlers to use later, and none of these tests reaches a query. Initialising it would
    pull in migrations for a gate check that never touches a table.
    """
    return collect_routers(
        gate=AdminGate("pw"),
        nav=NavRegistry(),
        db=Database("sqlite+aiosqlite://"),
    )


async def _answer_through(router: Router, *, amount: int, payload: str = "deposit:1") -> list[dict[str, Any]]:
    """Run every pre_checkout handler on this router and collect what it answered."""
    query = SimpleNamespace(
        id="q1",
        invoice_payload=payload,
        total_amount=amount,
        currency="XTR",
    )
    answers: list[dict[str, Any]] = []

    async def answer(**kwargs: Any) -> None:
        answers.append(kwargs)

    query.answer = answer
    for handler in router.pre_checkout_query.handlers:
        await handler.callback(query)
    return answers


async def test_a_real_deposit_is_approved() -> None:
    """The happy path - and the one that was broken."""
    answers = await _answer_through(
        _production_routers()[0], amount=service.DEPOSIT_AMOUNT_STARS
    )
    assert answers, "no pre_checkout handler was attached at all"
    assert answers[-1] == {"ok": True}, answers


async def test_the_wrong_amount_is_refused() -> None:
    """499 instead of 500 must not pass: this is the check the pin bump enabled."""
    answers = await _answer_through(_production_routers()[0], amount=499)
    assert answers, "no pre_checkout handler was attached at all"
    assert answers[-1].get("ok") is False, answers
    assert answers[-1].get("error_message") == "Неверная сумма", answers


async def test_declaring_nothing_refuses_everything() -> None:
    """What the old code did, kept as the reason this file exists.

    Attaching with no expectation is exactly what production did before the fix. The handler
    answers "Покупка не настроена" rather than approving - core fails closed - which is why
    the undeclared gate cost real deposits instead of silently approving a forged one. If
    someone deletes `expected_amount` from app.py, `test_a_real_deposit_is_approved` fails.
    """
    router = Router(name="undeclared")
    attach_payment_handlers(router, MockPaymentProvider())
    answers = await _answer_through(router, amount=service.DEPOSIT_AMOUNT_STARS)
    assert answers, "no pre_checkout handler was attached at all"
    assert answers[-1] == {
        "ok": False,
        "error_message": "Покупка не настроена",
    }, answers


def test_the_invoice_and_the_gate_read_one_constant() -> None:
    """Both ends must read DEPOSIT_AMOUNT_STARS, not two copies of 500.

    Behavioural tests cannot see the invoice amount until an invoice is created, so this is
    a source check - the only way to catch the two drifting apart while both still pass
    their own tests. One side changed to 600 and the other left at 500 would refuse every
    deposit, which is the same failure that shipped.
    """
    handlers = (ROOT / "src" / "booking" / "handlers.py").read_text(encoding="utf-8")
    app = (ROOT / "src" / "app.py").read_text(encoding="utf-8")

    assert "service.DEPOSIT_AMOUNT_STARS" in handlers, (
        "the invoice no longer reads the shared deposit amount"
    )
    assert "amount=500" not in handlers, (
        "the invoice hardcodes the deposit amount again"
    )
    assert "expected_amount=booking_service.DEPOSIT_AMOUNT_STARS" in app, (
        "the pre_checkout gate no longer declares the amount it expects"
    )
