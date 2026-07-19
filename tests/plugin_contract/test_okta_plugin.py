"""Validates whytrail's okta plugin against a real
okta.exceptions.exceptions.ApiException -- the class actually raised
by API calls (dispatched by status code via its own from_response()),
not the empty pass-through okta.exceptions.OktaAPIException. No live
Okta org or API token needed."""

from __future__ import annotations

import pytest

okta = pytest.importorskip("okta")
pytest.importorskip("whytrail.integrations.okta")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from okta.exceptions.exceptions import ApiException  # noqa: E402

SECRET_USER = "user secret.person@example.com"


def _api_exception(data=None):
    return ApiException(status=404, reason="Not Found", data=data if data is not None else {"errorSummary": SECRET_USER})


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ApiException) is not None


def test_why_on_api_exception_shows_status_and_reason():
    explanation = whytrail.why(_api_exception())
    assert explanation.known
    assert "404" in explanation.text
    assert "Not Found" in explanation.text


def test_detail_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_USER in detail_step.locals["detail"]
    assert SECRET_USER not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_USER not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ApiException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_exception())
    assert "overridden by the user" in explanation.text
