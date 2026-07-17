"""Validates whytrail-honeybadger's context construction and redaction
behavior by patching honeybadger.honeybadger.notify -- no live
Honeybadger account needed, same reasoning as whytrail-newrelic's
test."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("honeybadger")
pytest.importorskip("whytrail.integrations.honeybadger")

import whytrail  # noqa: E402
import whytrail.integrations.honeybadger as whytrail_honeybadger  # noqa: E402

SECRET = "sk-super-secret-token"


def _explanation_with_secret():
    try:
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")
    except ValueError as exc:
        return whytrail.why(exc)


def test_record_passes_context():
    explanation = _explanation_with_secret()
    with patch("honeybadger.honeybadger.notify") as mock_notify:
        whytrail_honeybadger.record(explanation, exception=ValueError("payment failed"))
    assert mock_notify.called
    context = mock_notify.call_args.kwargs["context"]
    assert "whytrail" in context
    assert "payment failed" in str(context)


def test_record_redacts_locals_by_default():
    explanation = _explanation_with_secret()
    with patch("honeybadger.honeybadger.notify") as mock_notify:
        whytrail_honeybadger.record(explanation, exception=ValueError("payment failed"))
    context = mock_notify.call_args.kwargs["context"]
    assert SECRET not in str(context)


def test_record_include_locals_true_opts_in():
    explanation = _explanation_with_secret()
    with patch("honeybadger.honeybadger.notify") as mock_notify:
        whytrail_honeybadger.record(explanation, exception=ValueError("payment failed"), include_locals=True)
    context = mock_notify.call_args.kwargs["context"]
    assert SECRET in str(context)
