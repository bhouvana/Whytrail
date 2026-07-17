"""Validates the confluent_kafka integration against a real
KafkaException wrapping a real KafkaError, constructed the same way
librdkafka's own bindings construct one internally."""

from __future__ import annotations

import pytest

ck = pytest.importorskip("confluent_kafka")
pytest.importorskip("whytrail.integrations.confluent_kafka")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_TOPIC = "Unknown topic: secret_customer_topic"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(ck.KafkaException) is not None


def test_why_on_kafka_exception_shows_name():
    error = ck.KafkaError(ck.KafkaError._UNKNOWN_TOPIC, reason="Unknown topic: x", fatal=False, retriable=True)
    exc = ck.KafkaException(error)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "_UNKNOWN_TOPIC" in explanation.text
    assert "retriable=True" in explanation.text


def test_broker_message_is_in_locals_and_strippable_via_redacted():
    error = ck.KafkaError(ck.KafkaError._UNKNOWN_TOPIC, reason=SECRET_TOPIC, fatal=False, retriable=True)
    exc = ck.KafkaException(error)
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_TOPIC in message_step.locals["message"]
    assert SECRET_TOPIC not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_TOPIC not in redacted.text
    assert "_UNKNOWN_TOPIC" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ck.KafkaException, lambda exc: "overridden by the user")
    error = ck.KafkaError(ck.KafkaError._UNKNOWN_TOPIC, reason="x", fatal=False, retriable=True)
    exc = ck.KafkaException(error)
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
