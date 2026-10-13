"""The admin gate must be the shared class, not a private copy.

Four bots carried a vendored copy of `botkit_core.admin.AdminGate` in
`src/core/auth.py`. Five copies of one class means five places for a security fix to land
in only some of them, and the copies had already drifted: `reminder`'s is a different
design. A copy that is textually identical today is not a guarantee about tomorrow.

Identity, not equality. `AdminGate is CoreAdminGate` fails the moment someone redefines
the class here, which is the moment this stops being the shared implementation.
"""
from __future__ import annotations

import ast
import pathlib
import re

from botkit_core.admin import AdminGate as CoreAdminGate

AUTH = pathlib.Path(__file__).resolve().parents[1] / "src" / "core" / "auth.py"


def test_the_module_exposes_the_shared_class() -> None:
    from src.core.auth import AdminGate

    assert AdminGate is CoreAdminGate, (
        "src/core/auth.py no longer re-exports botkit_core.admin.AdminGate. "
        "Import it from botkit_core.admin instead of defining a private copy - two "
        "classes answering to the same name is how the copies drifted apart."
    )


def test_auth_defines_no_admin_gate_of_its_own() -> None:
    """A subclass would also pass the identity check above, so exclude that here."""
    tree = ast.parse(AUTH.read_text(encoding="utf-8"))
    local = [
        node.name
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "AdminGate"
    ]
    assert not local, (
        "src/core/auth.py defines its own AdminGate class. Re-export the shared one "
        "instead; a subclass would let the two implementations diverge again."
    )


def test_the_re_export_is_explicit() -> None:
    """`import X as X` looks like a typo; it is what makes the re-export explicit.

    mypy runs with `no_implicit_reexport`, so a bare `from botkit_core.admin import
    AdminGate` is reported as "does not explicitly export attribute" everywhere it is
    imported. The alias form satisfies that. Written plainly, the next reader would
    "tidy" it away and the whole bot would fail its type check.
    """
    source = AUTH.read_text(encoding="utf-8")
    assert re.search(r"^from botkit_core\.admin import AdminGate as AdminGate$", source, re.M), (
        "the re-export must use the explicit `import AdminGate as AdminGate` form; mypy "
        "runs with no_implicit_reexport and a bare import is not an explicit re-export"
    )


def test_the_gate_still_guards_the_admin_surface() -> None:
    """Identity is necessary, not sufficient - the contract still has to hold."""
    gate = CoreAdminGate("right", [7])

    assert gate.is_admin(7) is True, "a configured admin id must pass"
    assert gate.is_admin(1) is False
    assert gate.authorize(1, "wrong") is False
    assert gate.is_admin(1) is False, "a failed attempt must not authorise"

    # Five wrong guesses exhaust the window; the throttle is what bounds the guesses.
    for _ in range(4):
        gate.authorize(1, "wrong")
    assert gate.is_throttled(1) is True

    # The gate accepts a correct password even while throttled: an admin who typed the
    # right thing is not locked out, and the throttle only bounds what reaches compare.
    assert gate.authorize(1, "right") is True
    assert gate.is_admin(1) is True
    assert gate.is_throttled(1) is False, "a success must clear the attempt list"

    gate.deauthorize(1)
    assert gate.is_admin(1) is False, "deauthorize must revoke"
    assert gate.is_admin(7) is True, "deauthorize must not touch configured admins"

