"""Validates whytrail-sentry end to end against the real sentry_sdk
pipeline (init -> capture_exception -> before_send -> transport), not
a mock of the hook signature."""

from __future__ import annotations

import pytest

sentry_sdk = pytest.importorskip("sentry_sdk")
whytrail_sentry = pytest.importorskip("whytrail_sentry")

from sentry_sdk.transport import Transport  # noqa: E402


class _CapturingTransport(Transport):
    def __init__(self):
        super().__init__({"dsn": "https://abc@example.com/1"})
        self.envelopes = []

    def capture_envelope(self, envelope):
        self.envelopes.append(envelope)


def _init(**kwargs):
    transport = _CapturingTransport()
    sentry_sdk.init(dsn="https://abc@example.com/1", transport=transport, **kwargs)
    return transport


def _captured_whytrail_context(transport):
    sentry_sdk.flush()
    for envelope in transport.envelopes:
        for item in envelope.items:
            payload = item.payload.json
            context = payload.get("contexts", {}).get("whytrail")
            if context:
                return context
    return None


def test_before_send_attaches_whytrail_context():
    transport = _init(before_send=whytrail_sentry.before_send)
    try:
        try:
            raise ValueError("root cause")
        except ValueError as e:
            raise KeyError("surface") from e
    except KeyError:
        sentry_sdk.capture_exception()

    context = _captured_whytrail_context(transport)
    assert context is not None
    assert "root cause" in context["text"]
    assert context["confidence"] == 1.0


def test_before_send_redacts_locals_by_default():
    transport = _init(before_send=whytrail_sentry.before_send)
    try:
        api_key = "sk-super-secret"  # noqa: F841
        raise ValueError("boom")
    except ValueError:
        sentry_sdk.capture_exception()

    context = _captured_whytrail_context(transport)
    assert context is not None
    assert "sk-super-secret" not in context["text"]
    assert "sk-super-secret" not in str(context["steps"])


def test_before_send_include_locals_true_opts_in():
    import functools

    transport = _init(before_send=functools.partial(whytrail_sentry.before_send, include_locals=True))
    try:
        api_key = "sk-super-secret"  # noqa: F841
        raise ValueError("boom")
    except ValueError:
        sentry_sdk.capture_exception()

    context = _captured_whytrail_context(transport)
    assert context is not None
    assert "sk-super-secret" in context["text"]


def test_chain_preserves_existing_before_send():
    calls = []

    def my_hook(event, hint):
        calls.append("my_hook")
        event.setdefault("tags", {})["custom"] = "yes"
        return event

    transport = _init(before_send=whytrail_sentry.chain(my_hook))
    try:
        raise ValueError("boom")
    except ValueError:
        sentry_sdk.capture_exception()

    sentry_sdk.flush()
    assert calls == ["my_hook"]
    envelope = transport.envelopes[0]
    payload = envelope.items[0].payload.json
    assert payload["tags"]["custom"] == "yes"
    assert "whytrail" in payload["contexts"]


def test_events_without_exceptions_are_untouched():
    transport = _init(before_send=whytrail_sentry.before_send)
    sentry_sdk.capture_message("just a message, no exception")
    sentry_sdk.flush()
    assert len(transport.envelopes) == 1
    payload = transport.envelopes[0].items[0].payload.json
    assert "whytrail" not in payload.get("contexts", {})
