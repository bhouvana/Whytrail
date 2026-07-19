"""Validates whytrail's mistralai plugin against real
mistralai.client.errors.MistralError objects, constructed the same way
the SDK constructs them internally from an httpx.Response -- no live
API calls or API keys needed."""

from __future__ import annotations

import pytest

mistralai = pytest.importorskip("mistralai")
httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail.integrations.mistralai")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from mistralai.client import errors as mistralai_errors  # noqa: E402

SECRET_PROMPT = "my secret business plan"


def _mistral_error(status_code=422, body=None):
    request = httpx.Request("POST", "https://api.mistral.ai/v1/chat/completions")
    response = httpx.Response(status_code, request=request, text=body or f"invalid request: {SECRET_PROMPT}")
    return mistralai_errors.SDKError("Unprocessable Entity", raw_response=response)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(mistralai_errors.MistralError) is not None


def test_why_on_sdk_error_shows_status():
    explanation = whytrail.why(_mistral_error())
    assert explanation.known
    assert "422" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_mistral_error())
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PROMPT in body_step.locals["body"]
    assert SECRET_PROMPT not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_PROMPT not in redacted.text
    assert "422" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(mistralai_errors.MistralError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_mistral_error())
    assert "overridden by the user" in explanation.text
