"""Validates whytrail's dropbox plugin against a real
dropbox.exceptions.ApiError -- no live Dropbox account needed."""

from __future__ import annotations

import pytest

dropbox = pytest.importorskip("dropbox")
pytest.importorskip("whytrail.integrations.dropbox")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from dropbox.exceptions import ApiError  # noqa: E402

SECRET_PATH = "/customers/secret-contract.pdf"


def _api_error(error=None):
    return ApiError(
        request_id="req-abc-123",
        error=error if error is not None else f"path/not_found: {SECRET_PATH}",
        user_message_text=None,
        user_message_locale=None,
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ApiError) is not None


def test_why_on_api_error_shows_request_id():
    explanation = whytrail.why(_api_error())
    assert explanation.known
    assert "req-abc-123" in explanation.text


def test_error_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PATH in detail_step.locals["error"]
    assert SECRET_PATH not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_PATH not in redacted.text
    assert "req-abc-123" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ApiError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_error())
    assert "overridden by the user" in explanation.text
