"""Validates the elasticsearch integration against a real
elasticsearch.NotFoundError raised through the client's actual HTTP
transport -- a real request/response round trip against a throwaway
local HTTP server standing in for a cluster, no live Elasticsearch
needed."""

from __future__ import annotations

import http.server
import json
import threading

import pytest

elasticsearch = pytest.importorskip("elasticsearch")
pytest.importorskip("whytrail.integrations.elasticsearch")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_QUERY_FRAGMENT = "customer_ssn:123-45-6789"


class _Handler(http.server.BaseHTTPRequestHandler):
    def _respond(self):
        length = int(self.headers.get("Content-Length", 0))
        if length:
            self.rfile.read(length)
        self.send_response(self.server.status_code)  # type: ignore[attr-defined]
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.server.body).encode())  # type: ignore[attr-defined]

    def do_GET(self):  # noqa: N802
        self._respond()

    def do_POST(self):  # noqa: N802
        self._respond()

    def log_message(self, *args):
        pass


@pytest.fixture()
def es_client():
    def _make(status_code, body):
        srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        srv.status_code = status_code  # type: ignore[attr-defined]
        srv.body = body  # type: ignore[attr-defined]
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        client = elasticsearch.Elasticsearch(f"http://127.0.0.1:{srv.server_port}")
        try:
            yield client
        finally:
            srv.shutdown()

    return _make


def test_plugin_is_discovered():
    assert registry.resolve_explainer(elasticsearch.ApiError) is not None


def test_why_on_not_found_shows_status_and_type(es_client):
    gen = es_client(
        404,
        {"error": {"type": "index_not_found_exception", "reason": "no such index [orders]", "index": "orders"}, "status": 404},
    )
    client = next(gen)
    with pytest.raises(elasticsearch.NotFoundError) as excinfo:
        client.get(index="orders", id="1")

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "index_not_found_exception" in explanation.text
    assert "status=404" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted(es_client):
    gen = es_client(
        400,
        {"error": {"type": "parsing_exception", "reason": SECRET_QUERY_FRAGMENT}, "status": 400},
    )
    client = next(gen)
    with pytest.raises(elasticsearch.ApiError) as excinfo:
        client.search(index="orders", query={"match": {"q": "x"}})

    explanation = whytrail.why(excinfo.value)
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_QUERY_FRAGMENT in body_step.locals["body"]
    assert SECRET_QUERY_FRAGMENT not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_QUERY_FRAGMENT not in redacted.text
    assert "status=400" in redacted.text  # structural detail survives redaction


def test_manual_registration_still_overrides_the_plugin(es_client):
    gen = es_client(404, {"error": {"type": "index_not_found_exception", "reason": "x", "index": "y"}, "status": 404})
    client = next(gen)
    whytrail.register(elasticsearch.ApiError, lambda exc: "overridden by the user")
    with pytest.raises(elasticsearch.NotFoundError) as excinfo:
        client.get(index="orders", id="1")
    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text
