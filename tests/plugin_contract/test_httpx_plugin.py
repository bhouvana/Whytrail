"""Validates whytrail-httpx against a real httpx.HTTPStatusError raised
through httpx's own MockTransport -- no live network needed, but a
real request/response round trip through httpx's actual client."""

from __future__ import annotations

import pytest

httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail_httpx")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def _client(status=404, body=b'{"error":"not found"}'):
    def handler(request):
        return httpx.Response(status, content=body, request=request)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(httpx.HTTPStatusError) is not None
    assert registry.resolve_explainer(httpx.RequestError) is not None


def test_why_on_status_error_shows_method_url_and_body():
    client = _client(status=500, body=b"db is down")
    resp = client.get("https://api.example.com/orders/1")
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        resp.raise_for_status()

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "GET" in explanation.text
    assert "500" in explanation.text
    assert "db is down" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    client = _client(status=500, body=b"db is down: user secret@example.com")
    resp = client.get("https://api.example.com/orders/1")
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        resp.raise_for_status()

    explanation = whytrail.why(excinfo.value)
    body_step = next(s for s in explanation.steps if s.locals)
    assert "secret@example.com" in body_step.locals["body"]
    assert "secret@example.com" not in body_step.description

    redacted = explanation.redacted()
    assert "secret@example.com" not in redacted.text
    assert "500" in redacted.text


def test_why_on_successful_status_has_no_body_step():
    client = _client(status=200, body=b"ok")
    resp = client.get("https://api.example.com/orders/1")
    # raise_for_status on a 200 doesn't raise; construct directly to
    # exercise the explainer's is_success branch
    resp.request = resp.request
    error = httpx.HTTPStatusError("test", request=resp.request, response=resp)
    explanation = whytrail.why(error)
    assert len(explanation.steps) == 1


def test_why_on_request_error():
    def handler(request):
        raise httpx.ConnectError("connection refused", request=request)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with pytest.raises(httpx.ConnectError) as excinfo:
        client.get("https://api.example.com/orders/1")

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "connection refused" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(httpx.HTTPStatusError, lambda exc: "overridden by the user")
    client = _client(status=404)
    resp = client.get("https://api.example.com/orders/1")
    with pytest.raises(httpx.HTTPStatusError) as excinfo:
        resp.raise_for_status()

    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text
