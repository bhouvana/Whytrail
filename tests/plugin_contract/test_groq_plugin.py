"""Validates whytrail's groq plugin against real groq SDK exception
objects, constructed the same way the SDK constructs them internally
from an httpx.Response -- no live API calls or API keys needed."""

from __future__ import annotations

import pytest

groq = pytest.importorskip("groq")
httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail.integrations.groq")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_PROMPT = "my secret business plan"


def _rate_limit_error(body=None):
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, request=request, json={"error": {"message": "Rate limit exceeded"}})
    return groq.RateLimitError(
        "Rate limit exceeded",
        response=response,
        body=body if body is not None else {"message": "Rate limit exceeded", "code": "rate_limit_exceeded"},
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(groq.APIStatusError) is not None
    assert registry.resolve_explainer(groq.APIConnectionError) is not None


def test_why_on_rate_limit_error_shows_status():
    explanation = whytrail.why(_rate_limit_error())
    assert explanation.known
    assert "429" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    exc = _rate_limit_error(body={"message": SECRET_PROMPT, "code": "content_filter"})
    explanation = whytrail.why(exc)
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PROMPT in body_step.locals["body"]
    assert SECRET_PROMPT not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_PROMPT not in redacted.text
    assert "429" in redacted.text


def test_connection_error():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    exc = groq.APIConnectionError(message="connection refused", request=request)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "connection refused" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(groq.APIStatusError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_rate_limit_error())
    assert "overridden by the user" in explanation.text
