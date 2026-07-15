"""Validates whytrail-grpcio against a real grpc.RpcError, raised by a
real in-process gRPC server/client round trip over loopback (no
external network, no .proto compilation needed -- grpc's generic
handler API takes raw byte serializers) -- not a hand-built mock
exception."""

from __future__ import annotations

from concurrent import futures

import pytest

grpc = pytest.importorskip("grpc")
pytest.importorskip("whytrail.integrations.grpcio")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_DETAIL = "order not found: secret@example.com"


@pytest.fixture()
def rpc_error():
    def handler(request, context):
        context.abort(grpc.StatusCode.NOT_FOUND, SECRET_DETAIL)

    rpc_handler = grpc.unary_unary_rpc_method_handler(
        handler, request_deserializer=lambda b: b, response_serializer=lambda b: b
    )
    generic_handler = grpc.method_handlers_generic_handler("test.Service", {"Get": rpc_handler})

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=1))
    server.add_generic_rpc_handlers((generic_handler,))
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()

    channel = grpc.insecure_channel(f"127.0.0.1:{port}")
    stub = channel.unary_unary(
        "/test.Service/Get", request_serializer=lambda b: b, response_deserializer=lambda b: b
    )
    try:
        stub(b"req")
    except grpc.RpcError as exc:
        yield exc
    finally:
        channel.close()
        server.stop(0)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(grpc.RpcError) is not None


def test_why_shows_status_code(rpc_error):
    explanation = whytrail.why(rpc_error)
    assert explanation.known
    assert "NOT_FOUND" in explanation.text


def test_details_is_in_locals_not_description(rpc_error):
    explanation = whytrail.why(rpc_error)
    details_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_DETAIL in details_step.locals["details"]
    assert SECRET_DETAIL not in details_step.description


def test_redacted_hides_details_but_keeps_status_code(rpc_error):
    explanation = whytrail.why(rpc_error).redacted()
    assert SECRET_DETAIL not in explanation.text
    assert "NOT_FOUND" in explanation.text


def test_manual_registration_still_overrides_the_plugin(rpc_error):
    whytrail.register(grpc.RpcError, lambda exc: "overridden by the user")
    explanation = whytrail.why(rpc_error)
    assert "overridden by the user" in explanation.text
