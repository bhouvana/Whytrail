"""Validates whytrail's algoliasearch plugin against a real
algoliasearch.http.exceptions.RequestException -- no live Algolia
index or API key needed."""

from __future__ import annotations

import pytest

algoliasearch = pytest.importorskip("algoliasearch")
pytest.importorskip("whytrail.integrations.algoliasearch")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from algoliasearch.http.exceptions import RequestException  # noqa: E402

SECRET_INDEX = "customers_secret_index"


def _request_exception(message=None):
    return RequestException(message if message is not None else f"Index {SECRET_INDEX} does not exist", 404)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(RequestException) is not None


def test_why_on_request_exception_shows_status_code():
    explanation = whytrail.why(_request_exception())
    assert explanation.known
    assert "404" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_request_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_INDEX in detail_step.locals["message"]
    assert SECRET_INDEX not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_INDEX not in redacted.text
    assert "404" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(RequestException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_request_exception())
    assert "overridden by the user" in explanation.text
