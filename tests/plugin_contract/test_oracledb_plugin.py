"""Validates the oracledb integration against a real oracledb.Error,
triggered by a real (thin-mode) connection attempt against an
unreachable host -- no live Oracle database needed, but a real driver
object nonetheless (unlike psycopg2's C-level attributes, oracledb's
`_Error` populates even without ever reaching a server)."""

from __future__ import annotations

import pytest

oracledb = pytest.importorskip("oracledb")
pytest.importorskip("whytrail.integrations.oracledb")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def _real_connection_error() -> "oracledb.Error":
    try:
        oracledb.connect(user="x", password="y", dsn="127.0.0.1:1/nonexistent", tcp_connect_timeout=2)
    except oracledb.Error as exc:
        return exc
    raise AssertionError("expected oracledb.connect() to fail against an unreachable host")


def test_plugin_is_discovered():
    assert registry.resolve_explainer(oracledb.Error) is not None


def test_why_on_connection_error_shows_full_code():
    exc = _real_connection_error()
    explanation = whytrail.why(exc)
    assert explanation.known
    detail = exc.args[0]
    assert detail.full_code in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = _real_connection_error()
    detail = exc.args[0]
    explanation = whytrail.why(exc)
    message_step = next((s for s in explanation.steps if s.locals), None)
    assert message_step is not None
    assert detail.message in message_step.locals["message"]
    assert detail.message not in message_step.description

    redacted = explanation.redacted()
    assert detail.message not in redacted.text
    assert detail.full_code in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(oracledb.Error, lambda exc: "overridden by the user")
    exc = _real_connection_error()
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
