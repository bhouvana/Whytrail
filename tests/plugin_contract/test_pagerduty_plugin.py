"""Validates whytrail's pagerduty plugin against a real
pagerduty.HttpError wrapping a real httpx.Response -- no live
PagerDuty account needed."""

from __future__ import annotations

import pytest

pagerduty = pytest.importorskip("pagerduty")
httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail.integrations.pagerduty")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_INCIDENT = "incident for secret-customer-outage"


def _http_error(msg=None):
    request = httpx.Request("GET", "https://api.pagerduty.com/incidents/P123")
    response = httpx.Response(404, request=request)
    return pagerduty.HttpError(msg if msg is not None else f"Not found: {SECRET_INCIDENT}", response)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(pagerduty.HttpError) is not None


def test_why_on_http_error_shows_status():
    explanation = whytrail.why(_http_error())
    assert explanation.known
    assert "404" in explanation.text


def test_msg_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_http_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_INCIDENT in detail_step.locals["msg"]
    assert SECRET_INCIDENT not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_INCIDENT not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pagerduty.HttpError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_http_error())
    assert "overridden by the user" in explanation.text
