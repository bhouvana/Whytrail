"""Validates whytrail's arango plugin against a real
arango.exceptions.ArangoServerError built from real
arango.response.Response/arango.request.Request objects -- no live
ArangoDB instance needed."""

from __future__ import annotations

import pytest

arango = pytest.importorskip("arango")
pytest.importorskip("whytrail.integrations.arango")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from arango.exceptions import ArangoServerError, DocumentGetError  # noqa: E402
from arango.response import Response  # noqa: E402
from arango.request import Request  # noqa: E402

SECRET_KEY = "customer/secret-doc-key-000"


def _server_error(error_message=None):
    response = Response(
        method="get",
        url=f"https://arango.example.com/_db/mydb/_api/document/{SECRET_KEY}",
        headers={},
        status_code=404,
        status_text="Not Found",
        raw_body='{"errorNum": 1202, "errorMessage": "document not found"}',
    )
    response.error_code = 1202
    response.error_message = error_message if error_message is not None else f"document not found: {SECRET_KEY}"
    request = Request(method="get", endpoint=f"/_api/document/{SECRET_KEY}")
    return DocumentGetError(response, request)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(ArangoServerError) is not None


def test_why_on_server_error_shows_http_and_arango_codes():
    explanation = whytrail.why(_server_error())
    assert explanation.known
    assert "404" in explanation.text
    assert "1202" in explanation.text


def test_message_and_url_are_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_server_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_KEY in detail_step.locals["message"]
    assert SECRET_KEY in detail_step.locals["url"]
    assert SECRET_KEY not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_KEY not in redacted.text
    assert "1202" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(ArangoServerError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_server_error())
    assert "overridden by the user" in explanation.text
