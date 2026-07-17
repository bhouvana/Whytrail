"""Validates the pyodbc integration against a real pyodbc.Error,
constructed with a real ODBC SQLSTATE code the same way pyodbc's own
C extension raises one on a driver error."""

from __future__ import annotations

import pytest

pyodbc = pytest.importorskip("pyodbc")
pytest.importorskip("whytrail.integrations.pyodbc")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_TABLE = "secret_customer_table"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(pyodbc.Error) is not None


def test_why_on_error_shows_sqlstate():
    exc = pyodbc.Error("42S02", "[Microsoft][ODBC Driver] Invalid object name.")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "42S02" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = pyodbc.Error("42S02", f"[Microsoft][ODBC Driver] Invalid object name '{SECRET_TABLE}'.")
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_TABLE in message_step.locals["message"]
    assert SECRET_TABLE not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_TABLE not in redacted.text
    assert "42S02" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pyodbc.Error, lambda exc: "overridden by the user")
    exc = pyodbc.Error("42S02", "x")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
