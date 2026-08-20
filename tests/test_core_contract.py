from collections.abc import Iterator

import pytest
from aiogram import Router
from aiogram.types import Message

from src.core.auth import (
    ADMIN_GATE_ATTR,
    ROUTER_REQUIRES_ADMIN,
    AdminGate,
    mark_admin_router,
    require_admin,
)
from src.core.navigation import NavRegistry, NavSection, compose_message
from src.core.database import Database
from src.core.migrations import MigrationRegistry


def _walk(router: Router) -> Iterator[Router]:
    yield router
    for sub in router.sub_routers:
        yield from _walk(sub)


def test_auth_gate_fail_closed():
    gate = AdminGate("secret")
    assert not gate.is_admin(123)
    assert gate.authorize(123, "wrong") is False
    assert gate.is_throttled(123) is False


def test_mark_admin_router():
    router = Router(name="test_admin")
    result = mark_admin_router(router)
    assert getattr(result, ROUTER_REQUIRES_ADMIN, False) is True


def test_escape_html():
    from src.core.navigation import escape_html

    assert escape_html("<script>") == "&lt;script&gt;"
    assert escape_html("ok") == "ok"


def test_nav_registry():
    nav = NavRegistry()
    nav.register(NavSection(slug="test", title="Test"))
    assert nav.get("test") is not None
    assert nav.title("test") == "Test"
    assert nav.get("missing") is None


def test_compose_message():
    result = compose_message(["Раздел"], "Текст")
    assert "Раздел" in result
    assert "Текст" in result


def test_fsm_is_command():
    from src.core.fsm import is_command

    assert is_command("/start") is True
    assert is_command("hello") is False
    assert is_command(None) is False


def test_create_payment_provider_mock():
    from src.core.payments import create_payment_provider

    provider = create_payment_provider("mock")
    assert hasattr(provider, "create_invoice_link")
    assert hasattr(provider, "verify_payment")


def test_create_storage_memory():
    from src.core.storage import create_storage

    storage = create_storage(None)
    assert storage is not None
