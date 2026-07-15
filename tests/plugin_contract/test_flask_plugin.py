"""Validates whytrail-flask's safety boundaries end to end via a real
Flask app and test client -- same thoroughness bar as
test_fastapi_plugin.py/test_django_plugin.py: every default gets an
explicit test, not just the happy path."""

from __future__ import annotations

import logging

import pytest

flask = pytest.importorskip("flask")
pytest.importorskip("whytrail.integrations.flask")

import whytrail.integrations.flask as whytrail_flask  # noqa: E402
from flask import Flask  # noqa: E402

SECRET = "sk-super-secret-token"


def _make_app(**install_kwargs):
    app = Flask(__name__)
    whytrail_flask.install(app, **install_kwargs)

    @app.route("/boom")
    def boom():
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    return app


def test_production_default_response_has_no_explanation_at_all():
    client = _make_app().test_client()
    resp = client.get("/boom")
    assert resp.status_code == 500
    assert resp.get_json() == {"detail": "Internal Server Error"}
    assert SECRET not in resp.get_data(as_text=True)


def test_production_default_log_is_redacted(caplog):
    client = _make_app().test_client()
    with caplog.at_level(logging.ERROR, logger="whytrail.flask"):
        client.get("/boom")
    assert SECRET not in caplog.text
    assert "payment failed" in caplog.text


def test_debug_true_includes_explanation_but_still_redacts_locals():
    client = _make_app(debug=True).test_client()
    resp = client.get("/boom")
    body = resp.get_json()
    assert "why" in body
    assert "payment failed" in str(body)
    assert SECRET not in resp.get_data(as_text=True)


def test_app_debug_flag_is_respected_when_debug_kwarg_omitted():
    app = Flask(__name__)
    app.debug = True
    whytrail_flask.install(app)  # debug not passed -- should fall back to app.debug

    @app.route("/boom")
    def boom():
        raise ValueError("payment failed")

    client = app.test_client()
    resp = client.get("/boom")
    assert "why" in resp.get_json()


def test_include_locals_in_response_requires_explicit_opt_in_even_under_debug():
    client = _make_app(debug=True, include_locals_in_response=True).test_client()
    resp = client.get("/boom")
    assert SECRET in resp.get_data(as_text=True)  # only reachable via two explicit, separate opt-ins


def test_log_locals_true_includes_secret_in_log_but_response_still_safe(caplog):
    client = _make_app(log_locals=True).test_client()
    with caplog.at_level(logging.ERROR, logger="whytrail.flask"):
        resp = client.get("/boom")
    assert SECRET in caplog.text
    assert resp.get_json() == {"detail": "Internal Server Error"}  # response opt-in is separate from log opt-in


def test_successful_requests_are_unaffected():
    app = Flask(__name__)
    whytrail_flask.install(app)

    @app.route("/ok")
    def ok():
        return {"status": "fine"}

    client = app.test_client()
    resp = client.get("/ok")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "fine"}
