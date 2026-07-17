"""Validates whytrail-newrelic's attribute-flattening and redaction
behavior by patching newrelic.agent.notice_error -- no live New Relic
account needed, same reasoning as why a real APM connection isn't
required for whytrail-ddtrace's span-tag tests (the mechanism under
test is what whytrail builds and passes in, not New Relic's own
delivery)."""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytest.importorskip("newrelic")
pytest.importorskip("whytrail.integrations.newrelic")

import whytrail  # noqa: E402
import whytrail.integrations.newrelic as whytrail_newrelic  # noqa: E402

SECRET = "sk-super-secret-token"


def _explanation_with_secret():
    try:
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")
    except ValueError as exc:
        return whytrail.why(exc)


def test_record_passes_flattened_attributes():
    explanation = _explanation_with_secret()
    with patch("newrelic.agent.notice_error") as mock_notice:
        whytrail_newrelic.record(explanation)
    assert mock_notice.called
    attributes = mock_notice.call_args.kwargs["attributes"]
    assert any(k.startswith("whytrail.") for k in attributes)
    assert any("payment failed" in v for v in attributes.values())


def test_record_redacts_locals_by_default():
    explanation = _explanation_with_secret()
    with patch("newrelic.agent.notice_error") as mock_notice:
        whytrail_newrelic.record(explanation)
    attributes = mock_notice.call_args.kwargs["attributes"]
    assert SECRET not in str(attributes)


def test_record_include_locals_true_opts_in():
    explanation = _explanation_with_secret()
    with patch("newrelic.agent.notice_error") as mock_notice:
        whytrail_newrelic.record(explanation, include_locals=True)
    attributes = mock_notice.call_args.kwargs["attributes"]
    assert SECRET in str(attributes)
