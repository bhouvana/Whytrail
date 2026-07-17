"""Validates whytrail-rollbar's extra_data construction and redaction
behavior by patching rollbar.report_exc_info -- no live Rollbar
account needed, same reasoning as whytrail-newrelic's test."""

from __future__ import annotations

import sys
from unittest.mock import patch

import pytest

pytest.importorskip("rollbar")
pytest.importorskip("whytrail.integrations.rollbar")

import whytrail  # noqa: E402
import whytrail.integrations.rollbar as whytrail_rollbar  # noqa: E402

SECRET = "sk-super-secret-token"


def _explanation_with_secret():
    try:
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")
    except ValueError as exc:
        return whytrail.why(exc)


def test_record_passes_extra_data():
    explanation = _explanation_with_secret()
    with patch("rollbar.report_exc_info") as mock_report:
        whytrail_rollbar.record(explanation, exc_info=sys.exc_info())
    assert mock_report.called
    extra_data = mock_report.call_args.kwargs["extra_data"]
    assert "whytrail" in extra_data
    assert "payment failed" in str(extra_data)


def test_record_redacts_locals_by_default():
    explanation = _explanation_with_secret()
    with patch("rollbar.report_exc_info") as mock_report:
        whytrail_rollbar.record(explanation, exc_info=sys.exc_info())
    extra_data = mock_report.call_args.kwargs["extra_data"]
    assert SECRET not in str(extra_data)


def test_record_include_locals_true_opts_in():
    explanation = _explanation_with_secret()
    with patch("rollbar.report_exc_info") as mock_report:
        whytrail_rollbar.record(explanation, exc_info=sys.exc_info(), include_locals=True)
    extra_data = mock_report.call_args.kwargs["extra_data"]
    assert SECRET in str(extra_data)
