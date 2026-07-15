"""Validates the entry-point plugin architecture (ADR §06) end to end
using the real whytrail-requests distribution installed in this
environment -- not a mock of the registry, the actual
importlib.metadata entry-point discovery path."""

from __future__ import annotations

import pytest

requests = pytest.importorskip("requests")

import whytrail  # noqa: E402


def _make_response(status_code=404, reason="Not Found", url="https://api.example.com/orders", text="not found"):
    request = requests.PreparedRequest()
    request.method = "GET"
    request.url = url

    response = requests.Response()
    response.status_code = status_code
    response.reason = reason
    response.url = url
    response._content = text.encode()
    response.request = request
    return response, request


def test_plugin_is_discovered_via_entry_point_not_manual_registration():
    from whytrail import registry

    assert registry.resolve_explainer(requests.Response) is not None


def test_why_on_response_uses_plugin_not_generic_fallback():
    response, _ = _make_response(status_code=500, reason="Server Error", text="db is down")
    explanation = whytrail.why(response)
    assert explanation.known
    assert "500" in explanation.text
    assert "db is down" in explanation.text


def test_why_on_successful_response_has_no_body_step():
    response, _ = _make_response(status_code=200, reason="OK", text="")
    explanation = whytrail.why(response)
    assert len(explanation.steps) == 1


def test_body_is_in_locals_and_strippable_via_redacted():
    """Retrofitted after ADR 0002 §3 item 5's core fix (this plugin
    predates it): a response body can echo back request data the same
    way an LLM API's response body can, so it goes through the same
    redactable locals mechanism, not description text directly."""
    response, _ = _make_response(status_code=500, reason="Server Error", text="db is down: user secret@example.com")
    explanation = whytrail.why(response)
    body_step = next(s for s in explanation.steps if s.locals)
    assert "secret@example.com" in body_step.locals["body"]
    assert "secret@example.com" not in body_step.description

    redacted = explanation.redacted()
    assert "secret@example.com" not in redacted.text
    assert "500" in redacted.text


def test_why_on_request_exception_uses_domain_detail():
    response, request = _make_response(status_code=404, reason="Not Found")
    exc = requests.exceptions.HTTPError("404 Client Error", request=request, response=response)
    explanation = whytrail.why(exc)
    assert "GET" in explanation.text
    assert "404" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(requests.Response, lambda r: "overridden by the user")
    response, _ = _make_response()
    explanation = whytrail.why(response)
    assert "overridden by the user" in explanation.text
