"""Validates the pymssql integration against a real pymssql.Error."""

from __future__ import annotations

import pytest

pymssql = pytest.importorskip("pymssql")
pytest.importorskip("whytrail.integrations.pymssql")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_TABLE = "secret_customer_table"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(pymssql.Error) is not None


def test_why_on_operational_error_shows_code():
    exc = pymssql.OperationalError((208, b"Invalid object name 'x'."))
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "208" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = pymssql.OperationalError((208, f"Invalid object name '{SECRET_TABLE}'.".encode()))
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_TABLE in message_step.locals["message"]
    assert SECRET_TABLE not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_TABLE not in redacted.text
    assert "208" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pymssql.Error, lambda exc: "overridden by the user")
    exc = pymssql.OperationalError((208, b"x"))
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
