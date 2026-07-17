"""Validates the clickhouse integration against a real ClickHouseError,
constructed with code=/name= keyword args the same way
clickhouse-connect's own httpclient.py raises one internally from a
real HTTP error response."""

from __future__ import annotations

import pytest

ch_exceptions = pytest.importorskip("clickhouse_connect.driver.exceptions")
pytest.importorskip("whytrail.integrations.clickhouse")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_TABLE = "secret_customer_table"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(ch_exceptions.ClickHouseError) is not None


def test_why_on_database_error_shows_code_and_name():
    exc = ch_exceptions.DatabaseError("Code: 60. DB::Exception: Table x doesn't exist", code=60, name="UNKNOWN_TABLE")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "UNKNOWN_TABLE" in explanation.text
    assert "60" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = ch_exceptions.DatabaseError(
        f"Code: 60. DB::Exception: Table default.{SECRET_TABLE} doesn't exist", code=60, name="UNKNOWN_TABLE"
    )
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_TABLE in message_step.locals["message"]
    assert SECRET_TABLE not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_TABLE not in redacted.text
    assert "UNKNOWN_TABLE" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ch_exceptions.ClickHouseError, lambda exc: "overridden by the user")
    exc = ch_exceptions.DatabaseError("x", code=60, name="UNKNOWN_TABLE")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
