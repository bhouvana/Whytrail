"""Validates whytrail's cohere plugin against real cohere.errors.ApiError
objects -- no live Cohere API calls or API keys needed."""

from __future__ import annotations

import pytest

cohere = pytest.importorskip("cohere")
pytest.importorskip("whytrail.integrations.cohere")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from cohere.errors import NotFoundError, TooManyRequestsError  # noqa: E402
from cohere.core.api_error import ApiError  # noqa: E402

SECRET_PROMPT = "my secret business plan"


def _not_found_error(body=None):
    return NotFoundError(body=body if body is not None else {"message": f"model not found for prompt: {SECRET_PROMPT}"})


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ApiError) is not None


def test_why_on_not_found_error_shows_status():
    explanation = whytrail.why(_not_found_error())
    assert explanation.known
    assert "404" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_not_found_error())
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PROMPT in body_step.locals["body"]
    assert SECRET_PROMPT not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_PROMPT not in redacted.text
    assert "404" in redacted.text


def test_why_on_subclass_still_resolves_via_base_registration():
    explanation = whytrail.why(TooManyRequestsError(body={"message": "slow down"}))
    assert explanation.known
    assert "429" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ApiError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_not_found_error())
    assert "overridden by the user" in explanation.text
