"""Validates the stripe integration against real stripe.StripeError
objects, constructed the same way the SDK constructs them internally
from an API response -- no live API calls or API keys needed."""

from __future__ import annotations

import pytest

stripe = pytest.importorskip("stripe")
pytest.importorskip("whytrail.integrations.stripe")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_CUSTOMER_NAME = "Jane Q. Confidential"


def _card_error(json_body=None):
    return stripe.CardError(
        "Your card was declined.",
        param="number",
        code="card_declined",
        http_status=402,
        json_body=json_body if json_body is not None else {"error": {"decline_code": "insufficient_funds"}},
    )


def test_plugin_is_discovered():
    assert registry.resolve_explainer(stripe.StripeError) is not None


def test_why_on_card_error_shows_code_and_param():
    explanation = whytrail.why(_card_error())
    assert explanation.known
    assert "card_declined" in explanation.text
    assert "param=number" in explanation.text
    assert "http_status=402" in explanation.text


def test_json_body_is_in_locals_and_strippable_via_redacted():
    exc = _card_error(json_body={"error": {"message": SECRET_CUSTOMER_NAME}})
    explanation = whytrail.why(exc)
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_CUSTOMER_NAME in body_step.locals["json_body"]
    assert SECRET_CUSTOMER_NAME not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_CUSTOMER_NAME not in redacted.text
    assert "card_declined" in redacted.text  # code/param detail survives redaction


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(stripe.StripeError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_card_error())
    assert "overridden by the user" in explanation.text
