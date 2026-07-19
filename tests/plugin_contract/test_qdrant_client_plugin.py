"""Validates whytrail's qdrant-client plugin against real
qdrant_client.http.exceptions.UnexpectedResponse objects -- no live
Qdrant instance needed."""

from __future__ import annotations

import json

import pytest

qdrant_client = pytest.importorskip("qdrant_client")
pytest.importorskip("whytrail.integrations.qdrant_client")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from qdrant_client.http.exceptions import UnexpectedResponse  # noqa: E402

SECRET_PAYLOAD = "customer ssn 000-00-0000"


def _unexpected_response(status_code=400, content=None):
    body = content if content is not None else json.dumps({"status": {"error": SECRET_PAYLOAD}}).encode()
    return UnexpectedResponse(
        status_code=status_code,
        reason_phrase="Bad Request",
        content=body,
        headers={"content-type": "application/json"},
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(UnexpectedResponse) is not None


def test_why_on_unexpected_response_shows_status():
    explanation = whytrail.why(_unexpected_response())
    assert explanation.known
    assert "400" in explanation.text


def test_content_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_unexpected_response())
    content_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PAYLOAD in content_step.locals["content"]
    assert SECRET_PAYLOAD not in content_step.description

    redacted = explanation.redacted()
    assert SECRET_PAYLOAD not in redacted.text
    assert "400" in redacted.text


def test_non_json_content_falls_back_to_raw_bytes():
    explanation = whytrail.why(_unexpected_response(content=b"not json"))
    assert explanation.known
    content_step = next(s for s in explanation.steps if s.locals)
    assert "not json" in content_step.locals["content"]


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(UnexpectedResponse, lambda exc: "overridden by the user")
    explanation = whytrail.why(_unexpected_response())
    assert "overridden by the user" in explanation.text
