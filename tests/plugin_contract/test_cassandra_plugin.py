"""Validates the cassandra integration against a real cassandra.Unavailable
and cassandra.WriteTimeout -- and confirms the sibling InvalidRequest
(message-only, a different branch of the exception hierarchy) is
correctly left unhandled by this plugin."""

from __future__ import annotations

import pytest

cassandra = pytest.importorskip("cassandra")
pytest.importorskip("whytrail.integrations.cassandra")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def test_plugin_is_discovered():
    assert registry.resolve_explainer(cassandra.RequestExecutionException) is not None


def test_why_on_unavailable_shows_consistency_detail():
    exc = cassandra.Unavailable("Cannot achieve consistency level", consistency=4, required_replicas=3, alive_replicas=1)
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "required_replicas=3" in explanation.text
    assert "alive_replicas=1" in explanation.text


def test_why_on_write_timeout_shows_write_type():
    exc = cassandra.WriteTimeout(
        "Write timeout", consistency=4, required_responses=3, received_responses=1, write_type=0
    )
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "required_responses=3" in explanation.text


def test_invalid_request_is_not_handled_by_this_plugin():
    # InvalidRequest is under RequestValidationException, a sibling
    # branch with no structured data -- confirming the registration
    # boundary is where the docstring says it is, not accidentally wider.
    exc = cassandra.InvalidRequest("unconfigured table x")
    assert not isinstance(exc, cassandra.RequestExecutionException)


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(cassandra.RequestExecutionException, lambda exc: "overridden by the user")
    exc = cassandra.Unavailable("x", consistency=4, required_replicas=3, alive_replicas=1)
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
