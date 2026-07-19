"""Validates whytrail's wandb plugin against real wandb.errors.Error
and wandb.errors.CommError objects -- no live W&B server needed."""

from __future__ import annotations

import pytest

wandb = pytest.importorskip("wandb")
pytest.importorskip("whytrail.integrations.wandb")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from wandb.errors import Error, CommError  # noqa: E402

SECRET_PROJECT = "secret-internal-project"


def _plain_error(context=None):
    return Error(f"failed to log to project {SECRET_PROJECT}", context=context)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(Error) is not None


def test_why_on_plain_error_shows_type():
    explanation = whytrail.why(_plain_error())
    assert explanation.known
    assert "Error" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_plain_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PROJECT in detail_step.locals["message"]
    assert SECRET_PROJECT not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_PROJECT not in redacted.text


def test_context_is_in_locals_when_present():
    explanation = whytrail.why(_plain_error(context={"run_id": "abc123"}))
    detail_step = next(s for s in explanation.steps if s.locals)
    assert "abc123" in detail_step.locals["context"]


def test_comm_error_unwraps_to_the_real_underlying_exception():
    underlying = ConnectionRefusedError(f"connection refused: {SECRET_PROJECT}")
    exc = CommError("failed to communicate with W&B servers", exc=underlying)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "ConnectionRefusedError" in explanation.text
    assert SECRET_PROJECT in explanation.text  # unredacted why() shows full detail, matching tenacity/dagster


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(Error, lambda exc: "overridden by the user")
    explanation = whytrail.why(_plain_error())
    assert "overridden by the user" in explanation.text
