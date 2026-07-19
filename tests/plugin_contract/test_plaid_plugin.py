"""Validates whytrail's plaid plugin against real
plaid.exceptions.ApiException objects -- no live Plaid API calls or
credentials needed."""

from __future__ import annotations

import pytest

plaid = pytest.importorskip("plaid")
pytest.importorskip("whytrail.integrations.plaid")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from plaid.exceptions import ApiException  # noqa: E402

SECRET_ACCOUNT = "account-sandbox-secret-id"


def _api_exception(body=None):
    exc = ApiException(status=400, reason="Bad Request")
    exc.body = body if body is not None else f'{{"error_code": "ITEM_LOGIN_REQUIRED", "account_id": "{SECRET_ACCOUNT}"}}'
    return exc


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ApiException) is not None


def test_why_on_api_exception_shows_status_and_reason():
    explanation = whytrail.why(_api_exception())
    assert explanation.known
    assert "400" in explanation.text
    assert "Bad Request" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_exception())
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_ACCOUNT in body_step.locals["body"]
    assert SECRET_ACCOUNT not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_ACCOUNT not in redacted.text
    assert "400" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ApiException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_exception())
    assert "overridden by the user" in explanation.text
