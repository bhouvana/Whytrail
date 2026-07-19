"""Validates whytrail's chromadb plugin against a real
chromadb.errors.NotFoundError -- no live Chroma server needed."""

from __future__ import annotations

import pytest

chromadb = pytest.importorskip("chromadb")
pytest.importorskip("whytrail.integrations.chromadb")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from chromadb.errors import ChromaError, NotFoundError  # noqa: E402

SECRET_COLLECTION = "customer-secret-collection"


def _not_found_error(message=None):
    exc = NotFoundError(message if message is not None else f"Collection {SECRET_COLLECTION} does not exist")
    exc.trace_id = "trace-abc-123"
    return exc


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ChromaError) is not None


def test_why_on_not_found_error_shows_name_and_code():
    explanation = whytrail.why(_not_found_error())
    assert explanation.known
    assert "NotFoundError" in explanation.text
    assert "404" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_not_found_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_COLLECTION in detail_step.locals["message"]
    assert SECRET_COLLECTION not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_COLLECTION not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ChromaError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_not_found_error())
    assert "overridden by the user" in explanation.text
