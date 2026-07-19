"""Validates whytrail's twilio plugin against real
twilio.base.exceptions.TwilioRestException objects -- no live Twilio
API calls or credentials needed."""

from __future__ import annotations

import pytest

twilio = pytest.importorskip("twilio")
pytest.importorskip("whytrail.integrations.twilio")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from twilio.base.exceptions import TwilioRestException  # noqa: E402

SECRET_NUMBER = "+15555550100"


def _rest_exception(msg=None, details=None):
    return TwilioRestException(
        status=400,
        uri="/2010-04-01/Accounts/ACxxx/Messages.json",
        msg=msg if msg is not None else f"The 'To' number {SECRET_NUMBER} is not a valid phone number",
        code=21211,
        method="POST",
        details=details,
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(TwilioRestException) is not None


def test_why_on_rest_exception_shows_status_and_twilio_code():
    explanation = whytrail.why(_rest_exception())
    assert explanation.known
    assert "400" in explanation.text
    assert "21211" in explanation.text


def test_msg_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_rest_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_NUMBER in detail_step.locals["msg"]
    assert SECRET_NUMBER not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_NUMBER not in redacted.text
    assert "400" in redacted.text
    assert "21211" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(TwilioRestException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_rest_exception())
    assert "overridden by the user" in explanation.text
