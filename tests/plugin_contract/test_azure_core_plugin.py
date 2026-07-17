"""Validates the azure-core integration against a real
azure.core.exceptions.HttpResponseError raised from a real HTTP
response via azure-core's own RequestsTransport, against a throwaway
local HTTP server standing in for an Azure service endpoint -- no live
Azure resource needed."""

from __future__ import annotations

import http.server
import json
import threading

import pytest

azure_core = pytest.importorskip("azure.core")
pytest.importorskip("whytrail.integrations.azure_core")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from azure.core.exceptions import HttpResponseError  # noqa: E402
from azure.core.pipeline.transport import RequestsTransport  # noqa: E402
from azure.core.rest import HttpRequest  # noqa: E402

SECRET_REQUEST_ID = "req-id-customer-abc-123"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(self.server.status_code)  # type: ignore[attr-defined]
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.server.body).encode())  # type: ignore[attr-defined]

    def log_message(self, *args):
        pass


@pytest.fixture()
def http_error():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    srv.status_code = 404  # type: ignore[attr-defined]
    srv.body = {  # type: ignore[attr-defined]
        "error": {"code": "BlobNotFound", "message": f"The specified blob does not exist. RequestId:{SECRET_REQUEST_ID}"}
    }
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    transport = RequestsTransport()
    req = HttpRequest("GET", f"http://127.0.0.1:{srv.server_port}/blob")
    try:
        with transport:
            resp = transport.send(req)
            resp.read()
            yield HttpResponseError(response=resp)
    finally:
        srv.shutdown()


def test_plugin_is_discovered():
    assert registry.resolve_explainer(HttpResponseError) is not None


def test_why_on_http_response_error_shows_status_and_code(http_error):
    explanation = whytrail.why(http_error)
    assert explanation.known
    assert "Not Found" in explanation.text
    assert "status_code=404" in explanation.text
    assert "code=BlobNotFound" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted(http_error):
    explanation = whytrail.why(http_error)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_REQUEST_ID in message_step.locals["message"]
    assert SECRET_REQUEST_ID not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_REQUEST_ID not in redacted.text
    assert "code=BlobNotFound" in redacted.text  # structural detail survives redaction


def test_manual_registration_still_overrides_the_plugin(http_error):
    whytrail.register(HttpResponseError, lambda exc: "overridden by the user")
    explanation = whytrail.why(http_error)
    assert "overridden by the user" in explanation.text
