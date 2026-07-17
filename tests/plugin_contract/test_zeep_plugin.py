"""Validates the zeep integration against a real zeep.exceptions.Fault."""

from __future__ import annotations

import pytest

zeep_exceptions = pytest.importorskip("zeep.exceptions")
pytest.importorskip("whytrail.integrations.zeep")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_FIELD = "secret_account_number"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(zeep_exceptions.Fault) is not None


def test_why_on_fault_shows_code():
    exc = zeep_exceptions.Fault("Invalid request", code="Client")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "Client" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = zeep_exceptions.Fault(f"Invalid request: missing {SECRET_FIELD}", code="Client")
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_FIELD in message_step.locals["message"]
    assert SECRET_FIELD not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_FIELD not in redacted.text
    assert "Client" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(zeep_exceptions.Fault, lambda exc: "overridden by the user")
    exc = zeep_exceptions.Fault("x", code="Client")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
