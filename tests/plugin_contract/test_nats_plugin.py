"""Validates whytrail's nats-py plugin against a real
nats.js.errors.APIError -- no live NATS server needed."""

from __future__ import annotations

import pytest

nats = pytest.importorskip("nats")
pytest.importorskip("whytrail.integrations.nats")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from nats.js.errors import APIError  # noqa: E402

SECRET_STREAM = "customer-orders-prod"


def _api_error(description=None):
    return APIError(
        code=400,
        err_code=10071,
        description=description if description is not None else f"stream '{SECRET_STREAM}' sequence mismatch",
        stream="ORDERS",
        seq=42,
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(APIError) is not None


def test_why_on_api_error_shows_code_and_stream_coordinates():
    explanation = whytrail.why(_api_error())
    assert explanation.known
    assert "400" in explanation.text
    assert "10071" in explanation.text
    assert "ORDERS" in explanation.text
    assert "42" in explanation.text


def test_description_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_STREAM in detail_step.locals["description"]
    assert SECRET_STREAM not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_STREAM not in redacted.text
    assert "400" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(APIError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_error())
    assert "overridden by the user" in explanation.text
