"""Validates whytrail-elastic-apm's custom-context construction and
redaction behavior against a real (unconfigured) elasticapm.Client --
capture_exception() no-ops without a real server, so the mechanism
under test is what whytrail builds and passes in, not APM delivery."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

pytest.importorskip("elasticapm")
pytest.importorskip("whytrail.integrations.elastic_apm")

import whytrail  # noqa: E402
import whytrail.integrations.elastic_apm as whytrail_elastic_apm  # noqa: E402

SECRET = "sk-super-secret-token"


def _explanation_with_secret():
    try:
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")
    except ValueError as exc:
        return whytrail.why(exc)


def test_record_passes_custom_context():
    explanation = _explanation_with_secret()
    fake_client = MagicMock()
    whytrail_elastic_apm.record(explanation, client=fake_client)
    assert fake_client.capture_exception.called
    custom = fake_client.capture_exception.call_args.kwargs["custom"]
    assert "whytrail" in custom
    assert "payment failed" in str(custom)


def test_record_redacts_locals_by_default():
    explanation = _explanation_with_secret()
    fake_client = MagicMock()
    whytrail_elastic_apm.record(explanation, client=fake_client)
    custom = fake_client.capture_exception.call_args.kwargs["custom"]
    assert SECRET not in str(custom)


def test_record_include_locals_true_opts_in():
    explanation = _explanation_with_secret()
    fake_client = MagicMock()
    whytrail_elastic_apm.record(explanation, client=fake_client, include_locals=True)
    custom = fake_client.capture_exception.call_args.kwargs["custom"]
    assert SECRET in str(custom)


def test_record_no_ops_without_a_configured_client():
    import elasticapm

    explanation = _explanation_with_secret()
    assert elasticapm.get_client() is None
    whytrail_elastic_apm.record(explanation)  # must not raise
