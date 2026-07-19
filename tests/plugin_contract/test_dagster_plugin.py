"""Validates whytrail's dagster plugin against a real
DagsterExecutionStepExecutionError wrapping a real underlying
exception -- no live Dagster run needed."""

from __future__ import annotations

import sys

import pytest

dagster = pytest.importorskip("dagster")
pytest.importorskip("whytrail.integrations.dagster")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from dagster._core.errors import DagsterExecutionStepExecutionError, DagsterUserCodeExecutionError  # noqa: E402

SECRET_ROW = "row with ssn 000-00-0000"


def _step_execution_error():
    try:
        raise ValueError(f"bad input: {SECRET_ROW}")
    except ValueError as exc:
        exc_info = sys.exc_info()
        return DagsterExecutionStepExecutionError(
            "Error occurred while executing op",
            user_exception=exc,
            original_exc_info=exc_info,
            step_key="load_rows",
            op_name="load_rows_op",
            op_def_name="load_rows_op",
        )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(DagsterUserCodeExecutionError) is not None


def test_why_unwraps_to_the_real_underlying_exception():
    explanation = whytrail.why(_step_execution_error())
    assert explanation.known
    assert "load_rows" in explanation.text
    assert "load_rows_op" in explanation.text
    assert "ValueError" in explanation.text


def test_underlying_exceptions_own_message_is_not_redacted_by_this_plugin():
    """Plain ValueError message is not redacted by tier 1 -- same
    reasoning and same test shape as whytrail-tenacity's own recursive
    unwrap, confirming the recursive why() call actually delegates
    rather than just stringifying .user_exception."""
    explanation = whytrail.why(_step_execution_error())
    assert SECRET_ROW in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(DagsterUserCodeExecutionError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_step_execution_error())
    assert "overridden by the user" in explanation.text
