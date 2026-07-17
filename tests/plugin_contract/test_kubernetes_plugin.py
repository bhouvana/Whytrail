"""Validates the kubernetes integration against a real
kubernetes.client.exceptions.ApiException raised through the client's
actual HTTP request path -- a real request/response round trip against
a throwaway local HTTP server standing in for a cluster's API server,
no live Kubernetes needed. Direct construction (ApiException(status=,
reason=)) leaves .body as None, so this is the only way to get a real
object with .body actually populated."""

from __future__ import annotations

import http.server
import json
import threading

import pytest

kubernetes = pytest.importorskip("kubernetes")
pytest.importorskip("whytrail.integrations.kubernetes")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_POD_NAME = "customer-secret-pod-xyz"


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        self.send_response(self.server.status_code)  # type: ignore[attr-defined]
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(self.server.body).encode())  # type: ignore[attr-defined]

    def log_message(self, *args):
        pass


@pytest.fixture()
def k8s_api():
    from kubernetes.client import ApiClient, Configuration, CoreV1Api

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    srv.status_code = 404  # type: ignore[attr-defined]
    srv.body = {  # type: ignore[attr-defined]
        "kind": "Status",
        "status": "Failure",
        "message": f'pods "{SECRET_POD_NAME}" not found',
        "reason": "NotFound",
        "code": 404,
    }
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    cfg = Configuration()
    cfg.host = f"http://127.0.0.1:{srv.server_port}"
    api = CoreV1Api(ApiClient(configuration=cfg))
    try:
        yield api
    finally:
        srv.shutdown()


def test_plugin_is_discovered():
    assert registry.resolve_explainer(kubernetes.client.exceptions.ApiException) is not None


def test_why_on_api_exception_shows_status_and_reason(k8s_api):
    with pytest.raises(kubernetes.client.exceptions.ApiException) as excinfo:
        k8s_api.read_namespaced_pod(name=SECRET_POD_NAME, namespace="default")

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "Not Found" in explanation.text
    assert "status=404" in explanation.text


def test_body_is_in_locals_and_strippable_via_redacted(k8s_api):
    with pytest.raises(kubernetes.client.exceptions.ApiException) as excinfo:
        k8s_api.read_namespaced_pod(name=SECRET_POD_NAME, namespace="default")

    explanation = whytrail.why(excinfo.value)
    body_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_POD_NAME in body_step.locals["body"]
    assert SECRET_POD_NAME not in body_step.description

    redacted = explanation.redacted()
    assert SECRET_POD_NAME not in redacted.text
    assert "status=404" in redacted.text  # structural detail survives redaction


def test_manual_registration_still_overrides_the_plugin(k8s_api):
    whytrail.register(kubernetes.client.exceptions.ApiException, lambda exc: "overridden by the user")
    with pytest.raises(kubernetes.client.exceptions.ApiException) as excinfo:
        k8s_api.read_namespaced_pod(name=SECRET_POD_NAME, namespace="default")
    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text
