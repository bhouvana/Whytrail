"""Validates the tenacity integration against a real RetryError raised
by tenacity's own retry loop -- not hand-constructed, since the point
of this plugin is unwrapping exactly what tenacity itself produces."""

from __future__ import annotations

import pytest

tenacity = pytest.importorskip("tenacity")
pytest.importorskip("whytrail.integrations.tenacity")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_VALUE = "secret_config_value_xyz"


def _real_retry_error(message: str, attempts: int = 3) -> "tenacity.RetryError":
    def flaky():
        raise ValueError(message)

    try:
        for attempt in tenacity.Retrying(stop=tenacity.stop_after_attempt(attempts)):
            with attempt:
                flaky()
    except tenacity.RetryError as exc:
        return exc
    raise AssertionError("expected tenacity.Retrying to raise RetryError")


def test_plugin_is_discovered():
    assert registry.resolve_explainer(tenacity.RetryError) is not None


def test_why_unwraps_to_the_real_underlying_exception():
    exc = _real_retry_error("connection refused", attempts=3)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "3 attempt" in explanation.text
    assert "ValueError" in explanation.text
    assert "connection refused" in explanation.text


def test_underlying_exceptions_own_redaction_still_applies():
    exc = _real_retry_error(SECRET_VALUE, attempts=2)
    explanation = whytrail.why(exc)
    assert SECRET_VALUE in explanation.text  # plain ValueError message is not redacted by tier 1


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(tenacity.RetryError, lambda exc: "overridden by the user")
    exc = _real_retry_error("x", attempts=1)
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
