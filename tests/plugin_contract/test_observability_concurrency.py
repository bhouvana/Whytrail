"""Concurrency tests for the observability integrations
(docs/testing-maturity.md gap #3: "Sentry/OTel/ddtrace capture paths
are not tested under concurrent load"). Same shape as
test_web_concurrency.py and test_task_queue_concurrency.py: many
concurrent captures, each carrying a unique per-call secret with
locals attached (maximizing what would be observable if isolation
broke), asserting every captured record contains exactly its own
secret and never another call's.

All three integrations here read *implicit* per-thread state rather
than an explicitly passed identifier (Sentry's current scope/hub via
`sys.exc_info()`, ddtrace's current span via its own context
propagation, OTel's current span via `contextvars`) -- which is exactly
the kind of "no obvious shared-mutable-state path, by design" claim
this project has learned not to trust without running it (see
test_web_concurrency.py's own docstring for the same reasoning applied
to the web frameworks).
"""

from __future__ import annotations

import concurrent.futures
import threading

import pytest

N_CALLS = 30


def _secret_for(i: int) -> str:
    return f"sk-secret-token-{i:04d}"


def _assert_exactly_one_secret(text: str, n: int) -> set[str]:
    present = {_secret_for(i) for i in range(n) if _secret_for(i) in text}
    assert len(present) == 1, f"expected exactly one secret, found {present} in {text!r}"
    return present


# -- Sentry: concurrent capture_exception() through one shared client --

sentry_sdk = pytest.importorskip("sentry_sdk")
whytrail_sentry = pytest.importorskip("whytrail.integrations.sentry")

from sentry_sdk.transport import Transport  # noqa: E402


class _CapturingTransport(Transport):
    def __init__(self):
        super().__init__({"dsn": "https://abc@example.com/1"})
        self.envelopes = []
        self._lock = threading.Lock()

    def capture_envelope(self, envelope):
        with self._lock:
            self.envelopes.append(envelope)


def test_sentry_concurrent_captures_do_not_cross_contaminate():
    import functools

    transport = _CapturingTransport()
    sentry_sdk.init(
        dsn="https://abc@example.com/1",
        transport=transport,
        before_send=functools.partial(whytrail_sentry.before_send, include_locals=True),
    )

    def _fire(i: int) -> None:
        request_secret = _secret_for(i)  # noqa: F841
        try:
            raise ValueError(f"request {i} failed")
        except ValueError:
            sentry_sdk.capture_exception()

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_fire, range(N_CALLS)))

    sentry_sdk.flush()
    assert len(transport.envelopes) == N_CALLS

    found: set[str] = set()
    for envelope in transport.envelopes:
        for item in envelope.items:
            context = item.payload.json.get("contexts", {}).get("whytrail")
            if context:
                found |= _assert_exactly_one_secret(str(context), N_CALLS)
    assert found == {_secret_for(i) for i in range(N_CALLS)}


# -- ddtrace: concurrent spans, each thread recording its own current span

pytest.importorskip("ddtrace")
whytrail_ddtrace = pytest.importorskip("whytrail.integrations.ddtrace")

import whytrail  # noqa: E402
from ddtrace.trace import tracer  # noqa: E402


def test_ddtrace_concurrent_spans_do_not_cross_contaminate():
    def _fire(i: int):
        with tracer.trace(f"concurrency-test-span-{i}") as span:
            request_secret = _secret_for(i)  # noqa: F841
            try:
                raise ValueError(f"request {i} failed")
            except ValueError as exc:
                explanation = whytrail.why(exc)
            whytrail_ddtrace.record(explanation, include_locals=True)
            tags = {k: v for k, v in span.get_tags().items() if k.startswith("whytrail.")}
        return tags

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        all_tags = list(pool.map(_fire, range(N_CALLS)))

    found: set[str] = set()
    for tags in all_tags:
        found |= _assert_exactly_one_secret(str(tags), N_CALLS)
    assert found == {_secret_for(i) for i in range(N_CALLS)}


# -- OTel: concurrent spans via a real TracerProvider ------------------

otel_sdk_trace = pytest.importorskip("opentelemetry.sdk.trace")
pytest.importorskip("opentelemetry")

from whytrail import otel  # noqa: E402


def test_otel_concurrent_spans_do_not_cross_contaminate():
    from opentelemetry.sdk.trace import TracerProvider

    provider = TracerProvider()
    tracer_ = provider.get_tracer("whytrail-concurrency-tests")

    def _fire(i: int):
        with tracer_.start_as_current_span(f"concurrency-test-span-{i}") as span:
            request_secret = _secret_for(i)  # noqa: F841
            try:
                raise ValueError(f"request {i} failed")
            except ValueError as exc:
                explanation = whytrail.why(exc)
            otel.record(explanation, include_locals=True)
        return dict(span.events[0].attributes) if span.events else {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        all_attrs = list(pool.map(_fire, range(N_CALLS)))

    found: set[str] = set()
    for attrs in all_attrs:
        found |= _assert_exactly_one_secret(str(attrs), N_CALLS)
    assert found == {_secret_for(i) for i in range(N_CALLS)}
