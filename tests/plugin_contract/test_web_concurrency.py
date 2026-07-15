"""Concurrency tests for the safety-critical web middleware
(docs/testing-maturity.md gap #3): whytrail's design has no obvious
shared-mutable-state path for one request's data to leak into
another's response (why() builds a fresh Explanation per call; the
only shared state, the default provenance graph, is lock-protected and
read-only for a plain unhandled exception) -- but "no obvious path by
design" is exactly the kind of claim this project has learned not to
trust without running it. These tests fire many concurrent requests,
each carrying a unique per-request secret, with
include_locals_in_response=True (maximizing what would be observable
if isolation broke), and assert every response contains only its own
secret and never another request's.
"""

from __future__ import annotations

import concurrent.futures

import pytest

N_REQUESTS = 30


def _secret_for(i: int) -> str:
    return f"sk-secret-token-{i:04d}"


# -- FastAPI: thread-pool concurrency via TestClient -------------------
#
# Originally written with a raw httpx.AsyncClient + ASGITransport for
# genuine async concurrency, and it failed on a *single* request before
# concurrency even entered the picture: registering a handler for the
# bare `Exception` class makes Starlette's ServerErrorMiddleware
# re-raise the original exception *after* calling the handler, by
# design, so ASGI servers can still log it -- confirmed by reproducing
# with N_REQUESTS=1 outside pytest entirely. `TestClient`'s
# `raise_server_exceptions=False` exists specifically to suppress that
# for tests; raw ASGITransport has no equivalent. Switched to the same
# thread-pool + TestClient pattern as the Flask test below, which is
# also a legitimate concurrency model (FastAPI route handlers already
# run in a worker thread pool via Starlette's own run_in_threadpool).

fastapi = pytest.importorskip("fastapi")
pytest.importorskip("whytrail_fastapi")


def test_fastapi_concurrent_requests_do_not_cross_contaminate():
    import whytrail_fastapi
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    whytrail_fastapi.install(app, debug=True, include_locals_in_response=True)

    @app.get("/boom/{i}")
    def boom(i: int):
        request_secret = _secret_for(i)  # noqa: F841
        raise ValueError(f"request {i} failed")

    client = TestClient(app, raise_server_exceptions=False)

    def _fire(i: int) -> tuple[int, str]:
        return i, client.get(f"/boom/{i}").text

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_fire, range(N_REQUESTS)))

    assert len(results) == N_REQUESTS
    for i, body in results:
        own_secret = _secret_for(i)
        assert own_secret in body, f"response {i} is missing its own secret"
        for j in range(N_REQUESTS):
            if j != i:
                assert _secret_for(j) not in body, f"response {i} leaked secret belonging to request {j}"


# -- Flask / Django: thread-pool concurrency (WSGI's real model) ------

flask = pytest.importorskip("flask")
pytest.importorskip("whytrail_flask")


def test_flask_concurrent_requests_do_not_cross_contaminate():
    import whytrail_flask
    from flask import Flask

    app = Flask(__name__)
    whytrail_flask.install(app, debug=True, include_locals_in_response=True)

    @app.route("/boom/<int:i>")
    def boom(i):
        request_secret = _secret_for(i)  # noqa: F841
        raise ValueError(f"request {i} failed")

    app.testing = True
    client = app.test_client()

    def _fire(i: int):
        return i, client.get(f"/boom/{i}").get_data(as_text=True)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(_fire, range(N_REQUESTS)))

    assert len(results) == N_REQUESTS
    for i, body in results:
        own_secret = _secret_for(i)
        assert own_secret in body, f"response {i} is missing its own secret"
        for j in range(N_REQUESTS):
            if j != i:
                assert _secret_for(j) not in body, f"response {i} leaked secret belonging to request {j}"


django = pytest.importorskip("django")
pytest.importorskip("whytrail_django")


def test_django_concurrent_requests_do_not_cross_contaminate():
    import django.conf

    if not django.conf.settings.configured:
        django.conf.settings.configure(DEBUG=False, ALLOWED_HOSTS=["testserver"])
        django.setup()

    from django.test import RequestFactory
    from django.test.utils import override_settings

    import whytrail_django

    def _fire(i: int) -> tuple[int, str]:
        def raiser():
            request_secret = _secret_for(i)  # noqa: F841
            raise ValueError(f"request {i} failed")

        middleware = whytrail_django.WhytrailMiddleware(get_response=lambda request: None)
        request = RequestFactory().get(f"/boom/{i}")
        try:
            raiser()
        except ValueError as exc:
            response = middleware.process_exception(request, exc)
        return i, response.content.decode()

    # override_settings mutates django.conf.settings, a process-wide
    # singleton -- calling it concurrently from worker threads would
    # test Django's own thread-safety limitations, not whytrail's, so
    # the override is applied once here, outside the pool, rather than
    # per-call inside _fire.
    with override_settings(DEBUG=True, WHYTRAIL_INCLUDE_LOCALS_IN_RESPONSE=True):
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(_fire, range(N_REQUESTS)))

    assert len(results) == N_REQUESTS
    for i, body in results:
        own_secret = _secret_for(i)
        assert own_secret in body, f"response {i} is missing its own secret"
        for j in range(N_REQUESTS):
            if j != i:
                assert _secret_for(j) not in body, f"response {i} leaked secret belonging to request {j}"
