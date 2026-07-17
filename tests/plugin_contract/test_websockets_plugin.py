"""Validates the websockets integration against a real
websockets.exceptions.ConnectionClosedError, constructed with a real
Close frame the same way the library's own connection-close handling
does internally."""

from __future__ import annotations

import pytest

ws_exceptions = pytest.importorskip("websockets.exceptions")
ws_frames = pytest.importorskip("websockets.frames")
pytest.importorskip("whytrail.integrations.websockets")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_REASON = "query against secret_table failed"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(ws_exceptions.ConnectionClosed) is not None


def test_why_on_connection_closed_shows_code():
    exc = ws_exceptions.ConnectionClosedError(ws_frames.Close(1011, "internal error"), None)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "1011" in explanation.text


def test_reason_is_in_locals_and_strippable_via_redacted():
    exc = ws_exceptions.ConnectionClosedError(ws_frames.Close(1011, SECRET_REASON), None)
    explanation = whytrail.why(exc)
    reason_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_REASON in reason_step.locals["reason"]
    assert SECRET_REASON not in reason_step.description

    redacted = explanation.redacted()
    assert SECRET_REASON not in redacted.text
    assert "1011" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ws_exceptions.ConnectionClosed, lambda exc: "overridden by the user")
    exc = ws_exceptions.ConnectionClosedError(ws_frames.Close(1000, "bye"), None)
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
