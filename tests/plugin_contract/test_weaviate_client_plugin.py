"""Validates whytrail's weaviate-client plugin against real
weaviate.exceptions objects -- no live Weaviate instance needed."""

from __future__ import annotations

import pytest

weaviate = pytest.importorskip("weaviate")
httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail.integrations.weaviate_client")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from weaviate.exceptions import UnexpectedStatusCodeError, WeaviateQueryError  # noqa: E402

SECRET_PROPERTY = "customer email secret@example.com"


def _status_code_error(status_code=422, body=None):
    request = httpx.Request("POST", "https://weaviate.example.com/v1/objects")
    response = httpx.Response(
        status_code,
        request=request,
        json=body if body is not None else {"error": [{"message": SECRET_PROPERTY}]},
    )
    return UnexpectedStatusCodeError("Create object", response)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(UnexpectedStatusCodeError) is not None
    assert registry.resolve_explainer(WeaviateQueryError) is not None


def test_why_on_status_code_error_shows_status():
    explanation = whytrail.why(_status_code_error())
    assert explanation.known
    assert "422" in explanation.text


def test_error_detail_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_status_code_error())
    error_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PROPERTY in error_step.locals["error"]
    assert SECRET_PROPERTY not in error_step.description

    redacted = explanation.redacted()
    assert SECRET_PROPERTY not in redacted.text
    assert "422" in redacted.text


def test_why_on_query_error_shows_protocol_and_message():
    exc = WeaviateQueryError(SECRET_PROPERTY, "GraphQL")
    explanation = whytrail.why(exc)
    assert explanation.known
    error_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PROPERTY in error_step.locals["error"]
    assert SECRET_PROPERTY not in error_step.description


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(UnexpectedStatusCodeError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_status_code_error())
    assert "overridden by the user" in explanation.text
