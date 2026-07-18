from __future__ import annotations

import pytest

otel_sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")

import whytrail  # noqa: E402
from whytrail import otel  # noqa: E402


@pytest.fixture()
def recording_span():
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("whytrail-tests")
    with tracer.start_as_current_span("test-span") as span:
        yield span


def test_record_attaches_event_to_current_span(recording_span):
    try:
        raise ValueError("payment failed")
    except ValueError as exc:
        explanation = whytrail.why(exc)

    recorded = otel.record(explanation)
    assert recorded is True
    assert len(recording_span.events) == 1
    assert recording_span.events[0].name == "whytrail.explanation"


def test_record_redacts_locals_by_default(recording_span):
    def raiser():
        api_key = "sk-super-secret"  # noqa: F841
        raise ValueError("payment failed")

    try:
        raiser()
    except ValueError as exc:
        explanation = whytrail.why(exc)

    otel.record(explanation)
    attributes = dict(recording_span.events[0].attributes)
    assert "sk-super-secret" not in str(attributes)


def test_record_include_locals_true_opts_in(recording_span):
    def raiser():
        api_key = "sk-super-secret"  # noqa: F841
        raise ValueError("payment failed")

    try:
        raiser()
    except ValueError as exc:
        explanation = whytrail.why(exc)

    otel.record(explanation, include_locals=True)
    attributes = dict(recording_span.events[0].attributes)
    assert "sk-super-secret" in str(attributes)


def test_record_flattens_nested_steps_into_scalar_attributes(recording_span):
    try:
        raise ValueError("payment failed")
    except ValueError as exc:
        explanation = whytrail.why(exc)

    otel.record(explanation)
    attributes = dict(recording_span.events[0].attributes)
    assert attributes["subject"] == "ValueError: payment failed"
    assert "payment failed" in attributes["steps.0.description"]
    assert attributes["steps.0.confidence_label"] == "explicit"


def test_record_with_explicit_span_argument():
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer = provider.get_tracer("whytrail-tests")
    with tracer.start_as_current_span("explicit-span") as span:
        explanation = whytrail.why(ValueError("boom"))
        recorded = otel.record(explanation, span=span)
    assert recorded is True
    assert len(span.events) == 1


def test_record_returns_false_without_a_recording_span():
    explanation = whytrail.why(ValueError("no span active"))
    # outside any start_as_current_span block, the default tracer
    # provider hands back a non-recording span
    recorded = otel.record(explanation)
    assert recorded is False


def test_otel_module_import_error_without_extra(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def blocking_import(name, *args, **kwargs):
        if name == "opentelemetry" or name.startswith("opentelemetry."):
            raise ImportError("simulated: extra not installed")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocking_import)
    with pytest.raises(ImportError, match="otel"):
        otel._require_otel()
