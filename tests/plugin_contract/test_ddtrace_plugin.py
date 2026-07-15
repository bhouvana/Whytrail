"""Validates whytrail-ddtrace against a real ddtrace span (no agent
connection needed -- span tags are set locally regardless of whether
the trace is ever successfully flushed to a collector)."""

from __future__ import annotations

import pytest

pytest.importorskip("ddtrace")
pytest.importorskip("whytrail.integrations.ddtrace")

import whytrail  # noqa: E402
import whytrail.integrations.ddtrace as whytrail_ddtrace  # noqa: E402
from ddtrace.trace import tracer  # noqa: E402

SECRET = "sk-super-secret-token"


def _raise_with_secret():
    api_key = SECRET  # noqa: F841
    raise ValueError("payment failed")


def test_record_attaches_tags_to_current_span():
    with tracer.trace("test-span") as span:
        try:
            _raise_with_secret()
        except ValueError as exc:
            explanation = whytrail.why(exc)
        recorded = whytrail_ddtrace.record(explanation)
        assert recorded is True
        assert span.get_tag("whytrail.subject") is not None
        assert "payment failed" in span.get_tag("whytrail.subject")


def test_record_redacts_locals_by_default():
    with tracer.trace("test-span") as span:
        try:
            _raise_with_secret()
        except ValueError as exc:
            explanation = whytrail.why(exc)
        whytrail_ddtrace.record(explanation)
        all_tags = {k: v for k, v in span.get_tags().items() if k.startswith("whytrail.")}
        assert SECRET not in str(all_tags)


def test_record_include_locals_true_opts_in():
    with tracer.trace("test-span") as span:
        try:
            _raise_with_secret()
        except ValueError as exc:
            explanation = whytrail.why(exc)
        whytrail_ddtrace.record(explanation, include_locals=True)
        all_tags = {k: v for k, v in span.get_tags().items() if k.startswith("whytrail.")}
        assert SECRET in str(all_tags)


def test_record_returns_false_without_an_active_span():
    explanation = whytrail.why(ValueError("no span active"))
    recorded = whytrail_ddtrace.record(explanation)
    assert recorded is False
