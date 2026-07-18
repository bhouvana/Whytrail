"""Targeted fault injection at real points inside `why()` -- not a
generic "make every function fail" framework, but confirmation that
`why()`'s one actual documented promise (ADR §19: "never raises,
degrades to an honest 'unknown' Explanation instead") really holds when
the code paths it depends on fail with the specific exception types a
production process can actually raise: `MemoryError` under memory
pressure, `RecursionError` on deep structures, `OSError`/`PermissionError`
from anything that touches the filesystem indirectly (a plugin's own
code might), `ImportError` from a broken lazy-loaded plugin.

Also confirms the *boundary* of that promise, which is just as real a
property as the promise itself: `why()` catches `Exception`, not
`BaseException` -- a `KeyboardInterrupt` raised mid-resolution must
still propagate and actually stop the program, not get silently
swallowed because it happened to fire while explaining something.

Patch target note, a real mistake found writing this file and worth
recording: `why()`'s implementation (`_why_impl` in `whytrail/__init__.py`)
calls `resolve_explainer`/`explain_exception`/`_explain_from_graph` as
names in *that module's own* global namespace, populated by
`from .registry import ... resolve_explainer` at import time. Patching
`whytrail.registry.resolve_explainer` afterward does *not* affect that
call site -- `from X import Y` copies a reference into the importing
module's own namespace, it does not create a live alias back to `X`.
Every fault-injection target below patches the name as it lives on the
`whytrail` package itself (`monkeypatch.setattr(whytrail, "resolve_explainer",
...)`), which is the actual name `_why_impl`'s bytecode looks up. An
earlier version of the `resolve_explainer` and `KeyboardInterrupt`/
`SystemExit` tests patched `whytrail.registry` instead and passed
vacuously -- the simulated fault was never actually invoked, so the
assertions were trivially true regardless of whether `why()`'s
protection worked at all. Caught by two of those tests failing with
"DID NOT RAISE" once written as `pytest.raises(...)` checks rather than
truthiness checks -- exactly the class of mistake this whole exercise
is meant to catch, just in the test harness instead of the library.
"""

from __future__ import annotations

import pytest

import whytrail


@pytest.mark.parametrize(
    "exc_type",
    [MemoryError, RecursionError, OSError, PermissionError, ImportError, ValueError, KeyError],
)
def test_why_survives_resolve_explainer_raising(monkeypatch, exc_type):
    def _boom(cls):
        raise exc_type(f"simulated {exc_type.__name__} inside resolve_explainer")

    monkeypatch.setattr(whytrail, "resolve_explainer", _boom)
    explanation = whytrail.why(ValueError("boom"))
    assert isinstance(explanation, whytrail.Explanation)


@pytest.mark.parametrize(
    "exc_type",
    [MemoryError, RecursionError, OSError, PermissionError, ImportError],
)
def test_why_survives_explain_exception_raising(monkeypatch, exc_type):
    def _boom(exc, *, max_depth=8):
        raise exc_type(f"simulated {exc_type.__name__} inside explain_exception")

    monkeypatch.setattr(whytrail, "explain_exception", _boom)
    explanation = whytrail.why(ValueError("boom"))
    assert isinstance(explanation, whytrail.Explanation)
    # Degrades to the honest "unknown" shape (ADR §19), not a partial
    # or fabricated one.
    assert explanation.known is False


@pytest.mark.parametrize(
    "exc_type",
    [MemoryError, RecursionError, OSError, PermissionError],
)
def test_why_survives_explain_from_graph_raising(monkeypatch, exc_type):
    def _boom(obj, *, max_depth=8):
        raise exc_type(f"simulated {exc_type.__name__} inside _explain_from_graph")

    monkeypatch.setattr(whytrail, "_explain_from_graph", _boom)
    explanation = whytrail.why(object())
    assert isinstance(explanation, whytrail.Explanation)
    assert explanation.known is False


def test_why_survives_a_plugin_explainer_raising_arbitrary_exceptions():
    """A plugin's explainer function is already wrapped in its own
    try/except inside _why_impl -- confirmed here with a battery of
    exception types, not just the one a hand-written plugin bug might
    happen to raise."""
    for exc_type in (MemoryError, RecursionError, OSError, ImportError, RuntimeError):

        def _broken_explainer(obj, _exc_type=exc_type):
            raise _exc_type("simulated plugin failure")

        whytrail.register(ValueError, _broken_explainer)
        try:
            explanation = whytrail.why(ValueError("boom"))
            assert isinstance(explanation, whytrail.Explanation)
        finally:
            whytrail.registry.unregister(ValueError)


def test_why_does_not_swallow_keyboard_interrupt(monkeypatch):
    """The boundary of ADR §19's promise: why() catches Exception, not
    BaseException. A KeyboardInterrupt raised mid-resolution must still
    propagate -- silently swallowing it would make Ctrl+C stop working
    if it happened to fire while whytrail was explaining something."""

    def _boom(cls):
        raise KeyboardInterrupt("simulated Ctrl+C during resolution")

    monkeypatch.setattr(whytrail, "resolve_explainer", _boom)
    with pytest.raises(KeyboardInterrupt):
        whytrail.why(ValueError("boom"))


def test_why_does_not_swallow_system_exit(monkeypatch):
    """Same boundary, the other common BaseException-only case:
    SystemExit (raised by sys.exit()) must propagate too."""

    def _boom(cls):
        raise SystemExit(1)

    monkeypatch.setattr(whytrail, "resolve_explainer", _boom)
    with pytest.raises(SystemExit):
        whytrail.why(ValueError("boom"))
