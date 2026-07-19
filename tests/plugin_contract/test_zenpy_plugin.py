"""Validates whytrail's zenpy plugin against a real
zenpy.lib.exception.APIException wrapping a real requests.Response --
no live Zendesk account needed."""

from __future__ import annotations

import pytest

zenpy = pytest.importorskip("zenpy")
requests = pytest.importorskip("requests")
pytest.importorskip("whytrail.integrations.zenpy")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from zenpy.lib.exception import APIException  # noqa: E402

SECRET_TICKET = "ticket about secret-customer-complaint"


def _api_exception(text=None):
    response = requests.Response()
    response.status_code = 422
    response._content = (text if text is not None else f"Unprocessable: {SECRET_TICKET}").encode()
    return APIException("Zendesk API error", response=response)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(APIException) is not None


def test_why_on_api_exception_shows_status():
    explanation = whytrail.why(_api_exception())
    assert explanation.known
    assert "422" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_TICKET in detail_step.locals["body"]
    assert SECRET_TICKET not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_TICKET not in redacted.text
    assert "422" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(APIException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_exception())
    assert "overridden by the user" in explanation.text
