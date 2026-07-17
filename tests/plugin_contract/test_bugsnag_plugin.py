"""Validates whytrail-bugsnag's metadata construction and redaction
behavior by patching bugsnag.notify -- no live Bugsnag account needed,
same reasoning as whytrail-newrelic's test."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("bugsnag")
pytest.importorskip("whytrail.integrations.bugsnag")

import whytrail  # noqa: E402
import whytrail.integrations.bugsnag as whytrail_bugsnag  # noqa: E402

SECRET = "sk-super-secret-token"


def _explanation_and_exception_with_secret():
    try:
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")
    except ValueError as exc:
        return whytrail.why(exc), exc


def test_record_passes_metadata():
    explanation, exc = _explanation_and_exception_with_secret()
    with patch("bugsnag.notify") as mock_notify:
        whytrail_bugsnag.record(explanation, exception=exc)
    assert mock_notify.called
    metadata = mock_notify.call_args.kwargs["metadata"]
    assert "whytrail" in metadata
    assert "payment failed" in str(metadata)


def test_record_redacts_locals_by_default():
    explanation, exc = _explanation_and_exception_with_secret()
    with patch("bugsnag.notify") as mock_notify:
        whytrail_bugsnag.record(explanation, exception=exc)
    metadata = mock_notify.call_args.kwargs["metadata"]
    assert SECRET not in str(metadata)


def test_record_include_locals_true_opts_in():
    explanation, exc = _explanation_and_exception_with_secret()
    with patch("bugsnag.notify") as mock_notify:
        whytrail_bugsnag.record(explanation, exception=exc, include_locals=True)
    metadata = mock_notify.call_args.kwargs["metadata"]
    assert SECRET in str(metadata)
