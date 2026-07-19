"""Validates whytrail's auth0 plugin against real
auth0.authentication.exceptions.Auth0Error and
auth0.management.core.api_error.ApiError objects -- no live Auth0
tenant or credentials needed."""

from __future__ import annotations

import pytest

auth0 = pytest.importorskip("auth0")
pytest.importorskip("whytrail.integrations.auth0")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from auth0.authentication.exceptions import Auth0Error  # noqa: E402
from auth0.management.core.api_error import ApiError  # noqa: E402

SECRET_EMAIL = "secret.user@example.com"


def _authentication_error(content=None):
    return Auth0Error(
        status_code=403,
        error_code="invalid_grant",
        message="Wrong email or password",
        content=content if content is not None else {"email": SECRET_EMAIL},
    )


def _management_error(body=None):
    return ApiError(status_code=404, body=body if body is not None else {"message": f"user {SECRET_EMAIL} not found"})


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(Auth0Error) is not None
    assert registry.resolve_explainer(ApiError) is not None


def test_why_on_authentication_error_shows_status_and_error_code():
    explanation = whytrail.why(_authentication_error())
    assert explanation.known
    assert "403" in explanation.text
    assert "invalid_grant" in explanation.text


def test_authentication_content_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_authentication_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_EMAIL in detail_step.locals["content"]
    assert SECRET_EMAIL not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_EMAIL not in redacted.text
    assert "403" in redacted.text


def test_why_on_management_error_shows_status():
    explanation = whytrail.why(_management_error())
    assert explanation.known
    assert "404" in explanation.text


def test_management_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_management_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_EMAIL in detail_step.locals["body"]

    redacted = explanation.redacted()
    assert SECRET_EMAIL not in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(Auth0Error, lambda exc: "overridden by the user")
    explanation = whytrail.why(_authentication_error())
    assert "overridden by the user" in explanation.text
