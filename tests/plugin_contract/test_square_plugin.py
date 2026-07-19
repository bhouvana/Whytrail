"""Validates whytrail's square plugin against real
square.core.api_error.ApiError objects -- no live Square API calls or
credentials needed."""

from __future__ import annotations

import pytest

square = pytest.importorskip("square")
pytest.importorskip("whytrail.integrations.square")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from square.core.api_error import ApiError  # noqa: E402

SECRET_DETAIL = "card ending in 4242 belongs to a different customer"


def _api_error(body=None):
    return ApiError(
        status_code=402,
        body=body
        if body is not None
        else {"errors": [{"category": "PAYMENT_METHOD_ERROR", "code": "CARD_DECLINED", "detail": SECRET_DETAIL}]},
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ApiError) is not None


def test_why_on_api_error_shows_status_category_and_code():
    explanation = whytrail.why(_api_error())
    assert explanation.known
    assert "402" in explanation.text
    assert "PAYMENT_METHOD_ERROR" in explanation.text
    assert "CARD_DECLINED" in explanation.text


def test_detail_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_DETAIL in detail_step.locals["detail"]
    assert SECRET_DETAIL not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_DETAIL not in redacted.text
    assert "CARD_DECLINED" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ApiError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_error())
    assert "overridden by the user" in explanation.text
