"""Validates the snowflake integration against a real
snowflake.connector.errors.ProgrammingError."""

from __future__ import annotations

import pytest

sf_errors = pytest.importorskip("snowflake.connector.errors")
pytest.importorskip("whytrail.integrations.snowflake")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_TABLE = "SECRET_CUSTOMER_TABLE"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(sf_errors.Error) is not None


def test_why_on_programming_error_shows_errno_and_sqlstate():
    exc = sf_errors.ProgrammingError(msg="SQL compilation error: Object 'X' does not exist", errno=2003, sqlstate="42S02")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "2003" in explanation.text
    assert "42S02" in explanation.text


def test_query_and_message_are_in_locals_and_strippable_via_redacted():
    exc = sf_errors.ProgrammingError(
        msg=f"SQL compilation error: Object '{SECRET_TABLE}' does not exist",
        errno=2003,
        sqlstate="42S02",
        query=f"SELECT * FROM {SECRET_TABLE}",
    )
    explanation = whytrail.why(exc)
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_TABLE in detail_step.locals["message"]
    assert SECRET_TABLE in detail_step.locals["query"]
    assert SECRET_TABLE not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_TABLE not in redacted.text
    assert "2003" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(sf_errors.Error, lambda exc: "overridden by the user")
    exc = sf_errors.ProgrammingError(msg="x", errno=2003, sqlstate="42S02")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
