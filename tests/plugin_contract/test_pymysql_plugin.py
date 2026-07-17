"""Validates the pymysql integration against a real pymysql.err.Error."""

from __future__ import annotations

import pytest

pymysql = pytest.importorskip("pymysql")
pytest.importorskip("whytrail.integrations.pymysql")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_COLUMN = "secret_ssn_column"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(pymysql.err.Error) is not None


def test_why_on_operational_error_shows_errno():
    exc = pymysql.err.OperationalError(1054, "Unknown column 'x' in 'field list'")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "1054" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = pymysql.err.OperationalError(1054, f"Unknown column '{SECRET_COLUMN}' in 'field list'")
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_COLUMN in message_step.locals["message"]
    assert SECRET_COLUMN not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_COLUMN not in redacted.text
    assert "1054" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pymysql.err.Error, lambda exc: "overridden by the user")
    exc = pymysql.err.OperationalError(1054, "x")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
