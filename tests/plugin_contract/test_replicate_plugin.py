"""Validates whytrail's replicate plugin against a real
replicate.exceptions.ReplicateError -- no live Replicate API calls or
API tokens needed."""

from __future__ import annotations

import pytest

replicate = pytest.importorskip("replicate")
pytest.importorskip("whytrail.integrations.replicate")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from replicate.exceptions import ReplicateError  # noqa: E402

SECRET_INPUT = "prompt: my secret product launch"


def _replicate_error(detail=None):
    return ReplicateError(
        type="https://replicate.com/docs/reference/http#errors.invalid-input",
        title="Invalid input",
        status=422,
        detail=detail if detail is not None else f"invalid input: {SECRET_INPUT}",
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ReplicateError) is not None


def test_why_on_replicate_error_shows_title_and_status():
    explanation = whytrail.why(_replicate_error())
    assert explanation.known
    assert "Invalid input" in explanation.text
    assert "422" in explanation.text


def test_detail_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_replicate_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_INPUT in detail_step.locals["detail"]
    assert SECRET_INPUT not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_INPUT not in redacted.text
    assert "422" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ReplicateError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_replicate_error())
    assert "overridden by the user" in explanation.text
