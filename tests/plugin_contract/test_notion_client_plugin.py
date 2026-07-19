"""Validates whytrail's notion-client plugin against a real
notion_client.errors.HTTPResponseError -- no live Notion workspace
needed."""

from __future__ import annotations

import pytest

notion_client = pytest.importorskip("notion_client")
httpx = pytest.importorskip("httpx")
pytest.importorskip("whytrail.integrations.notion_client")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from notion_client.errors import HTTPResponseError  # noqa: E402

SECRET_PAGE = "page-secret-internal-roadmap"


def _http_response_error(raw_body_text=None):
    return HTTPResponseError(
        code="object_not_found",
        status=404,
        message="Could not find page",
        headers=httpx.Headers({"content-type": "application/json"}),
        raw_body_text=raw_body_text if raw_body_text is not None else f'{{"message": "{SECRET_PAGE} not found"}}',
        request_id="req-123",
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(HTTPResponseError) is not None


def test_why_on_http_response_error_shows_status_and_code():
    explanation = whytrail.why(_http_response_error())
    assert explanation.known
    assert "404" in explanation.text
    assert "object_not_found" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_http_response_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_PAGE in detail_step.locals["body"]
    assert SECRET_PAGE not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_PAGE not in redacted.text
    assert "object_not_found" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(HTTPResponseError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_http_response_error())
    assert "overridden by the user" in explanation.text
