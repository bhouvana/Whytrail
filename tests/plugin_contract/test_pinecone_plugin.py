"""Validates whytrail's pinecone plugin against real
pinecone.exceptions.PineconeApiException objects -- no live Pinecone
API calls or API keys needed."""

from __future__ import annotations

import pytest

pinecone = pytest.importorskip("pinecone")
pytest.importorskip("whytrail.integrations.pinecone")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from pinecone.exceptions import PineconeApiException  # noqa: E402

SECRET_INDEX = "my-secret-customer-index"


def _api_exception(body=None):
    return PineconeApiException(
        message="index not found",
        status_code=404,
        body=body if body is not None else {"message": f"index not found: {SECRET_INDEX}"},
        reason="Not Found",
        error_code="INDEX_NOT_FOUND",
        request_id="req-123",
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(PineconeApiException) is not None


def test_why_on_api_exception_shows_status_and_code():
    explanation = whytrail.why(_api_exception())
    assert explanation.known
    assert "404" in explanation.text
    assert "INDEX_NOT_FOUND" in explanation.text
    assert "req-123" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_exception())
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_INDEX in body_step.locals["body"]
    assert SECRET_INDEX not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_INDEX not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(PineconeApiException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_exception())
    assert "overridden by the user" in explanation.text
