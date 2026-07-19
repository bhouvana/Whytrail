"""Validates whytrail's meilisearch plugin against a real
meilisearch.errors.MeilisearchApiError wrapping a real
requests.Response -- no live Meilisearch instance needed."""

from __future__ import annotations

import json

import pytest

meilisearch = pytest.importorskip("meilisearch")
requests = pytest.importorskip("requests")
pytest.importorskip("whytrail.integrations.meilisearch")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from meilisearch.errors import MeilisearchApiError  # noqa: E402

SECRET_INDEX = "customer-records-secret"


def _api_error(message=None):
    response = requests.Response()
    response.status_code = 404
    response._content = json.dumps(
        {
            "message": message if message is not None else f"Index `{SECRET_INDEX}` not found",
            "code": "index_not_found",
            "type": "invalid_request",
            "link": "https://docs.meilisearch.com/errors#index_not_found",
        }
    ).encode()
    return MeilisearchApiError("index not found", response)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(MeilisearchApiError) is not None


def test_why_on_api_error_shows_status_and_code():
    explanation = whytrail.why(_api_error())
    assert explanation.known
    assert "404" in explanation.text
    assert "index_not_found" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_INDEX in detail_step.locals["message"]
    assert SECRET_INDEX not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_INDEX not in redacted.text
    assert "index_not_found" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(MeilisearchApiError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_error())
    assert "overridden by the user" in explanation.text
