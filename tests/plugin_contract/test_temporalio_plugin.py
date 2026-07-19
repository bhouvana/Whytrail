"""Validates whytrail's temporalio plugin against real
temporalio.exceptions.ApplicationError objects -- no live Temporal
server needed."""

from __future__ import annotations

from datetime import timedelta

import pytest

temporalio = pytest.importorskip("temporalio")
pytest.importorskip("whytrail.integrations.temporalio")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from temporalio.exceptions import ApplicationError  # noqa: E402

SECRET_PAYLOAD = "customer credit card 4242-4242-4242-4242"


def _application_error(details=()):
    return ApplicationError(
        "payment processing failed",
        *(details or (SECRET_PAYLOAD,)),
        type="PaymentError",
        non_retryable=True,
        next_retry_delay=timedelta(seconds=30),
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ApplicationError) is not None


def test_why_on_application_error_shows_type_and_retry_semantics():
    explanation = whytrail.why(_application_error())
    assert explanation.known
    assert "PaymentError" in explanation.text
    assert "non_retryable=True" in explanation.text


def test_details_are_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_application_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PAYLOAD in detail_step.locals["details"]
    assert SECRET_PAYLOAD not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_PAYLOAD not in redacted.text
    assert "PaymentError" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ApplicationError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_application_error())
    assert "overridden by the user" in explanation.text
