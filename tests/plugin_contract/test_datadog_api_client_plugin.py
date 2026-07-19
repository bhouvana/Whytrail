"""Validates whytrail's datadog-api-client plugin against a real
datadog_api_client.exceptions.ApiException -- no live Datadog account
needed."""

from __future__ import annotations

import pytest

datadog_api_client = pytest.importorskip("datadog_api_client")
pytest.importorskip("whytrail.integrations.datadog_api_client")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from datadog_api_client.exceptions import ApiException  # noqa: E402

SECRET_DASHBOARD = "dashboard secret-internal-metrics"


def _api_exception(body=None):
    exc = ApiException(status=404, reason="Not Found")
    exc.body = body if body is not None else f"{{'errors': ['{SECRET_DASHBOARD} not found']}}"
    return exc


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ApiException) is not None


def test_why_on_api_exception_shows_status_and_reason():
    explanation = whytrail.why(_api_exception())
    assert explanation.known
    assert "404" in explanation.text
    assert "Not Found" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_DASHBOARD in detail_step.locals["body"]

    redacted = explanation.redacted()
    assert SECRET_DASHBOARD not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ApiException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_exception())
    assert "overridden by the user" in explanation.text
