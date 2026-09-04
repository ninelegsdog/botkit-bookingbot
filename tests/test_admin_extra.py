"""Extra tests for admin handlers to boost coverage to 80%."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock
from aiogram.types import Message, Chat, User

from src.core.auth import AdminGate
from src.core.navigation import NavRegistry
from src.core.navigation import NavSection


def test_admin_gate_is_admin() -> None:
    gate = AdminGate(password="secret", admin_ids=[123, 456])
    assert gate.is_admin(123) is True
    assert gate.is_admin(456) is True
    assert gate.is_admin(999) is False


def test_admin_gate_authorize() -> None:
    gate = AdminGate(password="secret", admin_ids=[123])
    assert gate.authorize(999, "secret") is True
    assert gate.is_admin(999) is True  # now authorized
    assert gate.authorize(888, "wrong") is False
    assert gate.is_admin(888) is False


def test_nav_registry_register() -> None:
    registry = NavRegistry()
    section = NavSection(slug="test", title="Test")
    registry.register(section)
    assert registry.get("test") is not None
    assert registry.get("test").title == "Test"
    assert registry.title("test") == "Test"
    assert registry.title("nonexistent") == "nonexistent"


def test_admin_gate_with_empty_ids() -> None:
    gate = AdminGate(password="secret", admin_ids=[])
    assert gate.is_admin(123) is False
    assert gate.authorize(123, "secret") is True


def test_nav_registry_breadcrumbs() -> None:
    registry = NavRegistry()
    section = NavSection(slug="child", title="Child")
    registry.register(section)
    crumbs = registry.breadcrumbs("child")
    assert isinstance(crumbs, list)
