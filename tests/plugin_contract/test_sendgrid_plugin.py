"""Validates the sendgrid integration against a real
python_http_client.exceptions.HTTPError, constructed the same way the
sendgrid SDK itself constructs one internally on an API error
response."""

from __future__ import annotations

import pytest

sendgrid = pytest.importorskip("sendgrid")
http_exceptions = pytest.importorskip("python_http_client.exceptions")
pytest.importorskip("whytrail.integrations.sendgrid")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_FIELD = "attacker@evil.example.com leaked in body"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(http_exceptions.HTTPError) is not None


def test_why_on_bad_request_shows_status_and_reason():
    exc = http_exceptions.BadRequestsError(400, "Bad Request", b'{"errors":[{"message":"bad from field"}]}', {})
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "400" in explanation.text
    assert "Bad Request" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    body = f'{{"errors":[{{"message":"{SECRET_FIELD}"}}]}}'.encode()
    exc = http_exceptions.BadRequestsError(400, "Bad Request", body, {})
    explanation = whytrail.why(exc)
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_FIELD in body_step.locals["body"]
    assert SECRET_FIELD not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_FIELD not in redacted.text
    assert "400" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(http_exceptions.HTTPError, lambda exc: "overridden by the user")
    exc = http_exceptions.BadRequestsError(400, "Bad Request", b"{}", {})
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
