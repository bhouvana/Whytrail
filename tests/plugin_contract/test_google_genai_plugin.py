"""Validates the google_genai integration against a real
google.genai.errors.APIError, constructed the same way the SDK builds
one internally from a parsed API error response."""

from __future__ import annotations

import pytest

genai_errors = pytest.importorskip("google.genai.errors")
pytest.importorskip("whytrail.integrations.google_genai")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_MESSAGE = "invalid model_secret_key_xyz"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(genai_errors.APIError) is not None


def test_why_on_client_error_shows_code_and_status():
    exc = genai_errors.ClientError(
        400, {"error": {"code": 400, "message": "bad request", "status": "INVALID_ARGUMENT"}}
    )
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "400" in explanation.text
    assert "INVALID_ARGUMENT" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = genai_errors.ClientError(
        400, {"error": {"code": 400, "message": SECRET_MESSAGE, "status": "INVALID_ARGUMENT"}}
    )
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_MESSAGE in message_step.locals["message"]
    assert SECRET_MESSAGE not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_MESSAGE not in redacted.text
    assert "400" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(genai_errors.APIError, lambda exc: "overridden by the user")
    exc = genai_errors.ClientError(400, {"error": {"code": 400, "message": "x", "status": "INVALID_ARGUMENT"}})
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
