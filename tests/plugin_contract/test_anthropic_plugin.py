"""Validates whytrail-anthropic against real anthropic SDK exception
objects, constructed the same way the SDK does internally from an
httpx.Response -- no live API calls or API keys needed."""

from __future__ import annotations

import pytest

anthropic = pytest.importorskip("anthropic")
httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail.integrations.anthropic")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def _rate_limit_error(body=None):
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(429, request=request, json={"error": {"type": "rate_limit_error"}})
    return anthropic.RateLimitError(
        "Rate limited",
        response=response,
        body=body if body is not None else {"type": "rate_limit_error", "message": "Rate limited"},
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(anthropic.APIStatusError) is not None
    assert registry.resolve_explainer(anthropic.APIConnectionError) is not None


def test_why_on_rate_limit_error_shows_status_and_type():
    exc = _rate_limit_error()
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "429" in explanation.text
    assert "rate_limit_error" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    secret = "my proprietary prompt content"
    exc = _rate_limit_error(body={"type": "rate_limit_error", "message": secret})
    explanation = whytrail.why(exc)
    body_step = next(s for s in explanation.steps if s.locals)
    assert secret in body_step.locals["body"]
    assert secret not in body_step.description

    redacted = explanation.redacted()
    assert secret not in redacted.text
    assert "429" in redacted.text


def test_connection_error():
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    exc = anthropic.APIConnectionError(message="connection refused", request=request)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "connection refused" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(anthropic.APIStatusError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_rate_limit_error())
    assert "overridden by the user" in explanation.text
