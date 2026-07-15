"""Validates whytrail-aiohttp against a real aiohttp.web server/client
round trip over loopback (aiohttp's own TestServer/TestClient) -- not
a constructed mock exception. Driven via asyncio.run() in plain sync
test functions rather than adding a pytest-asyncio dependency just for
this one plugin's tests."""

from __future__ import annotations

import asyncio

import pytest

aiohttp = pytest.importorskip("aiohttp")
pytest.importorskip("whytrail_aiohttp")

from aiohttp import web  # noqa: E402
from aiohttp.test_utils import TestClient, TestServer  # noqa: E402

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


async def _get_response_error(status=500, text="db is down"):
    async def handler(request):
        return web.Response(status=status, text=text)

    app = web.Application()
    app.router.add_get("/orders/1", handler)

    async with TestClient(TestServer(app)) as client:
        resp = await client.get("/orders/1")
        try:
            resp.raise_for_status()
        except aiohttp.ClientResponseError as exc:
            return exc
    return None


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(aiohttp.ClientResponseError) is not None
    assert registry.resolve_explainer(aiohttp.ClientConnectionError) is not None


def test_why_on_response_error_shows_method_url_status():
    exc = asyncio.run(_get_response_error(status=500, text="db is down"))
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "GET" in explanation.text
    assert "500" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(aiohttp.ClientResponseError, lambda exc: "overridden by the user")
    exc = asyncio.run(_get_response_error())
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text


def test_connection_error():
    # Constructed directly rather than attempting a real refused
    # connection: "connect to an unused port" is not a reliable way to
    # provoke ClientConnectionError specifically across platforms (it
    # hung and hit aiohttp's own timeout instead, raising
    # asyncio.TimeoutError, when first tried against 127.0.0.1:1) --
    # same reasoning as whytrail-openai/anthropic's connection-error
    # tests, which construct the SDK's connection-error type directly
    # rather than depending on real network failure modes.
    connection_key = aiohttp.client_reqrep.ConnectionKey(
        host="example.invalid", port=443, is_ssl=True, ssl=None, proxy=None, proxy_auth=None, proxy_headers_hash=None
    )
    exc = aiohttp.ClientConnectorError(connection_key, OSError("connection refused"))
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "example.invalid" in explanation.text
