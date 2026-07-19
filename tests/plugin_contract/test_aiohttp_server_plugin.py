"""Validates whytrail-aiohttp-server's safety boundaries end to end via
a real aiohttp.web.Application and TestClient -- same thoroughness bar
as test_fastapi_plugin.py/test_flask_plugin.py/test_django_plugin.py:
every default gets an explicit test, not just the happy path. Driven
via asyncio.run() in plain sync test functions, the same pattern
test_aiohttp_plugin.py (the client-side explainer) already uses --
this project has no pytest-asyncio dependency."""

from __future__ import annotations

import asyncio
import dataclasses
import logging

import pytest

aiohttp = pytest.importorskip("aiohttp")
pytest.importorskip("whytrail.integrations.aiohttp_server")

import whytrail.integrations.aiohttp_server as whytrail_aiohttp  # noqa: E402
from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

SECRET = "sk-super-secret-token"


@dataclasses.dataclass
class _Result:
    status: int
    text: str


def _make_app(**install_kwargs):
    app = web.Application()
    whytrail_aiohttp.install(app, **install_kwargs)

    async def boom(request: web.Request) -> web.StreamResponse:
        api_key = SECRET  # noqa: F841
        raise ValueError("payment failed")

    async def ok(request: web.Request) -> web.StreamResponse:
        return web.json_response({"status": "fine"})

    app.router.add_get("/boom", boom)
    app.router.add_get("/ok", ok)
    return app


async def _get(app, path) -> _Result:
    # Read the body fully while the client/connection is still open --
    # a real bug caught writing this test: returning the raw
    # ClientResponse out of the `async with TestClient(...)` block and
    # reading it in the caller raises ClientConnectionError, since the
    # underlying connection is already torn down by the time the
    # context manager exits.
    async with TestClient(TestServer(app)) as client:
        resp = await client.get(path)
        text = await resp.text()
        return _Result(status=resp.status, text=text)


def test_production_default_response_has_no_explanation_at_all():
    result = asyncio.run(_get(_make_app(), "/boom"))
    assert result.status == 500
    assert "Internal Server Error" in result.text
    assert '"why"' not in result.text
    assert SECRET not in result.text


def test_production_default_log_is_redacted(caplog):
    with caplog.at_level(logging.ERROR, logger="whytrail.aiohttp_server"):
        asyncio.run(_get(_make_app(), "/boom"))
    assert SECRET not in caplog.text
    assert "payment failed" in caplog.text


def test_debug_true_includes_explanation_but_still_redacts_locals():
    result = asyncio.run(_get(_make_app(debug=True), "/boom"))
    assert '"why"' in result.text
    assert "payment failed" in result.text
    assert SECRET not in result.text


def test_include_locals_in_response_requires_explicit_opt_in_even_under_debug():
    result = asyncio.run(_get(_make_app(debug=True, include_locals_in_response=True), "/boom"))
    assert SECRET in result.text  # only reachable via two explicit, separate opt-ins


def test_log_locals_true_includes_secret_in_log_but_response_still_safe(caplog):
    with caplog.at_level(logging.ERROR, logger="whytrail.aiohttp_server"):
        result = asyncio.run(_get(_make_app(log_locals=True), "/boom"))
    assert "Internal Server Error" in result.text  # response opt-in is separate from log opt-in
    assert SECRET not in result.text
    assert SECRET in caplog.text


def test_successful_requests_are_unaffected():
    result = asyncio.run(_get(_make_app(), "/ok"))
    assert result.status == 200
    assert "fine" in result.text


def test_aiohttp_own_http_exceptions_pass_through_unchanged():
    result = asyncio.run(_get(_make_app(), "/does-not-exist"))
    assert result.status == 404
