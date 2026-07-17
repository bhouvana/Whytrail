"""Validates the pika integration against real pika.exceptions objects,
constructed the same way pika's own connection-adapter code constructs
them internally when a broker closes a channel/connection -- no live
RabbitMQ needed."""

from __future__ import annotations

import pytest

pika = pytest.importorskip("pika")
pytest.importorskip("whytrail.integrations.pika")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_QUEUE_NAME = "customer-ssn-queue"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(pika.exceptions.ChannelClosed) is not None
    assert registry.resolve_explainer(pika.exceptions.ConnectionClosed) is not None


def test_why_on_channel_closed_by_broker_shows_reply_code():
    exc = pika.exceptions.ChannelClosedByBroker(404, f"NOT_FOUND - no queue '{SECRET_QUEUE_NAME}'")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "reply_code=404" in explanation.text


def test_reply_text_is_in_locals_and_strippable_via_redacted():
    exc = pika.exceptions.ChannelClosedByBroker(404, f"NOT_FOUND - no queue '{SECRET_QUEUE_NAME}'")
    explanation = whytrail.why(exc)
    reply_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_QUEUE_NAME in reply_step.locals["reply_text"]
    assert SECRET_QUEUE_NAME not in reply_step.description

    redacted = explanation.redacted()
    assert SECRET_QUEUE_NAME not in redacted.text
    assert "reply_code=404" in redacted.text  # structural detail survives redaction


def test_why_on_connection_closed_by_broker():
    exc = pika.exceptions.ConnectionClosedByBroker(320, "CONNECTION_FORCED - broker shutdown")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "reply_code=320" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pika.exceptions.ChannelClosed, lambda exc: "overridden by the user")
    exc = pika.exceptions.ChannelClosedByBroker(404, "NOT_FOUND - no queue 'x'")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
