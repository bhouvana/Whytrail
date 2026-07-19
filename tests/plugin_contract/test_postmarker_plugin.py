"""Validates whytrail's postmarker plugin against a real
postmarker.exceptions.ClientError -- no live Postmark account needed."""

from __future__ import annotations

import pytest

postmarker = pytest.importorskip("postmarker")
pytest.importorskip("whytrail.integrations.postmarker")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from postmarker.exceptions import ClientError  # noqa: E402


def _client_error(error_code=406):
    return ClientError("Inactive recipient", error_code=error_code)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ClientError) is not None


def test_why_on_client_error_shows_error_code():
    explanation = whytrail.why(_client_error())
    assert explanation.known
    assert "406" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ClientError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_client_error())
    assert "overridden by the user" in explanation.text
