"""Validates whytrail-fastapi's safety boundaries end to end via a real
FastAPI app and TestClient -- this is the highest-severity item in the
whole ecosystem review (ADR 0002 §3 item 5), so every default gets an
explicit test, not just the happy path."""

from __future__ import annotations

import logging

import pytest

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("whytrail_fastapi")

import whytrail_fastapi  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

SECRET = "sk-super-secret-token"


def _make_app(**install_kwargs):
    app = FastAPI()
    whytrail_fastapi.install(app, **install_kwargs)

    @app.get("/boom")
    def boom():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    return app


def test_production_default_response_has_no_explanation_at_all():
    client = TestClient(_make_app(), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert resp.json() == {"detail": "Internal Server Error"}
    assert SECRET not in resp.text
    assert "ValueError" not in resp.text


def test_production_default_log_is_redacted(caplog):
    client = TestClient(_make_app(), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="whytrail.fastapi"):
        client.get("/boom")
    assert SECRET not in caplog.text
    assert "payment failed" in caplog.text  # the message itself is fine, just not the secret local


def test_debug_true_includes_explanation_but_still_redacts_locals():
    client = TestClient(_make_app(debug=True), raise_server_exceptions=False)
    resp = client.get("/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert "why" in body
    assert "payment failed" in str(body)
    assert SECRET not in resp.text


def test_debug_true_and_include_locals_in_response_true_is_the_only_way_to_leak():
    client = TestClient(
        _make_app(debug=True, include_locals_in_response=True), raise_server_exceptions=False
    )
    resp = client.get("/boom")
    assert SECRET in resp.text  # only reachable via two explicit, separate opt-ins


def test_log_locals_true_includes_secret_in_log_but_response_still_safe(caplog):
    client = TestClient(_make_app(log_locals=True), raise_server_exceptions=False)
    with caplog.at_level(logging.ERROR, logger="whytrail.fastapi"):
        resp = client.get("/boom")
    assert SECRET in caplog.text
    assert resp.json() == {"detail": "Internal Server Error"}  # response opt-in is separate from log opt-in


def test_successful_requests_are_unaffected():
    app = FastAPI()
    whytrail_fastapi.install(app)

    @app.get("/ok")
    def ok():
        return {"status": "fine"}

    client = TestClient(app)
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert resp.json() == {"status": "fine"}
