"""Validates the opensearch integration against a real
opensearchpy.exceptions.NotFoundError, constructed the same way
opensearch-py's own transport layer constructs one internally from a
real API response."""

from __future__ import annotations

import pytest

opensearchpy = pytest.importorskip("opensearchpy")
os_exceptions = pytest.importorskip("opensearchpy.exceptions")
pytest.importorskip("whytrail.integrations.opensearch")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_REASON = "no such index secret_customer_index"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(os_exceptions.TransportError) is not None


def test_why_on_not_found_shows_status_and_error():
    exc = os_exceptions.NotFoundError(
        404, "index_not_found_exception", {"error": {"type": "index_not_found_exception", "reason": "x"}, "status": 404}
    )
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "404" in explanation.text
    assert "index_not_found_exception" in explanation.text


def test_info_is_in_locals_and_strippable_via_redacted():
    exc = os_exceptions.NotFoundError(
        404,
        "index_not_found_exception",
        {"error": {"type": "index_not_found_exception", "reason": SECRET_REASON}, "status": 404},
    )
    explanation = whytrail.why(exc)
    info_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_REASON in info_step.locals["info"]
    assert SECRET_REASON not in info_step.description

    redacted = explanation.redacted()
    assert SECRET_REASON not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(os_exceptions.TransportError, lambda exc: "overridden by the user")
    exc = os_exceptions.NotFoundError(404, "index_not_found_exception", {})
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
