"""Validates whytrail-openai against real openai SDK exception objects,
constructed the same way the SDK constructs them internally from an
httpx.Response -- no live API calls or API keys needed."""

from __future__ import annotations

import pytest

openai = pytest.importorskip("openai")
httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail_openai")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_PROMPT = "my secret business plan"


def _rate_limit_error(body=None):
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    response = httpx.Response(429, request=request, json={"error": {"message": "Rate limit exceeded"}})
    return openai.RateLimitError(
        "Rate limit exceeded",
        response=response,
        body=body if body is not None else {"message": "Rate limit exceeded", "code": "rate_limit_exceeded"},
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(openai.APIStatusError) is not None
    assert registry.resolve_explainer(openai.APIConnectionError) is not None


def test_why_on_rate_limit_error_shows_status_and_code():
    exc = _rate_limit_error()
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "429" in explanation.text
    assert "rate_limit_exceeded" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    """Matches the established posture (ADR 0002 §3 item 5): .text on
    the raw Explanation shows full detail for local dev, same as
    tier-1's own locals capture -- redaction is something an
    integration opts into explicitly via .redacted() before exporting
    off-box, not a default on why() itself."""
    exc = _rate_limit_error(body={"message": SECRET_PROMPT, "code": "content_filter"})
    explanation = whytrail.why(exc)
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PROMPT in body_step.locals["body"]
    assert SECRET_PROMPT not in body_step.description  # not baked into unredactable text

    redacted = explanation.redacted()
    assert SECRET_PROMPT not in redacted.text
    assert "429" in redacted.text  # status detail survives redaction


def test_connection_error():
    request = httpx.Request("POST", "https://api.openai.com/v1/chat/completions")
    exc = openai.APIConnectionError(message="connection refused", request=request)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "connection refused" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(openai.APIStatusError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_rate_limit_error())
    assert "overridden by the user" in explanation.text
