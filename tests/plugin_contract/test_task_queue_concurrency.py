"""Concurrency tests for the task-queue integrations
(docs/testing-maturity.md gap #3: "the task-queue plugins (Celery/RQ/
dramatiq/Prefect) ... are not tested under concurrent load -- only
FastAPI, Flask, and Django are"). Same shape as
test_web_concurrency.py: fire many concurrent task/job/actor failures,
each carrying a unique per-call secret, with `log_locals=True`
(maximizing what would be observable if isolation broke -- the default
`log_locals=False` redacts every secret away entirely, which would make
a cross-contamination check vacuously pass whether or not isolation
actually held), and assert every logged record contains exactly its own
secret and no other call's.

Prefect is deliberately not included here: `whytrail.integrations.
prefect`'s own module docstring states it "does not capture task
arguments/parameters the way those three do" (no network call inside a
failure handler), so there is no locals-bearing, redaction-relevant
state for a cross-contamination test to exercise the way there is for
the other three -- adding one would just check that a fixed
"ValueError: boom" string doesn't contain other tasks' text, which
isn't a real property. Sentry/ddtrace/OTel's concurrency coverage
(also named in this gap) lives in test_observability_concurrency.py
instead, since none of them are task-queue integrations.

RQ's real `Worker` deliberately isn't exercised concurrently here, for
the same reason `test_rq_plugin.py` uses `SimpleWorker` instead of the
default `Worker`: RQ's own concurrency model for the default `Worker`
is `os.fork()`-based process isolation, not threads -- genuine data
leakage between jobs through Python-level shared state is structurally
impossible there regardless of anything whytrail does. What a threaded
or async-custom RQ deployment *could* exercise is whytrail's own
installed exception-handler function being called concurrently from
multiple job-processing contexts -- so this file calls that function
directly (the same object `install()` attaches to `Worker.
push_exc_handler`), via a stub worker, under real concurrent load, since
that's the actual whytrail-owned code path with any shared-state risk.
"""

from __future__ import annotations

import concurrent.futures
import logging
from types import SimpleNamespace

import pytest

N_CALLS = 30


def _secret_for(i: int) -> str:
    return f"sk-secret-token-{i:04d}"


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(self.format(record))


def _assert_no_cross_contamination(records: list[str], n: int) -> None:
    """Each record should carry exactly one call's secret, and the set
    of secrets found across all records should be exactly the full set
    -- proving both that no call's data went missing (completeness) and
    that no record picked up another call's secret (isolation)."""
    assert len(records) == n, f"expected {n} logged records, got {len(records)}"
    found: set[str] = set()
    for record in records:
        present = {_secret_for(i) for i in range(n) if _secret_for(i) in record}
        assert len(present) == 1, f"expected exactly one secret in record, found {present}: {record!r}"
        found |= present
    assert found == {_secret_for(i) for i in range(n)}, "some secret never appeared in any record"


# -- Celery: task_failure signal fired concurrently from worker threads -

celery = pytest.importorskip("celery")
pytest.importorskip("whytrail.integrations.celery")

import whytrail.integrations.celery as whytrail_celery  # noqa: E402
from celery import Celery  # noqa: E402
from celery.signals import task_failure  # noqa: E402


def test_celery_concurrent_task_failures_do_not_cross_contaminate():
    app = Celery("whytrail-celery-concurrency-tests", broker="memory://", backend="cache+memory://")

    @app.task(name="whytrail_tests.concurrency_flaky")
    def flaky(secret):
        raise ValueError("boom")

    logger = logging.getLogger("whytrail.celery.test.concurrency")
    logger.setLevel(logging.ERROR)
    handler = _ListHandler()
    logger.addHandler(handler)
    whytrail_celery.install(log_locals=True, logger=logger)

    def _fire(i: int) -> None:
        try:
            raise ValueError(f"task {i} failed")
        except ValueError as exc:
            task_failure.send(
                sender=flaky,
                task_id=f"task-{i}",
                exception=exc,
                args=[_secret_for(i)],
                kwargs={},
                traceback=None,
                einfo=None,
            )

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_fire, range(N_CALLS)))

    _assert_no_cross_contamination(handler.records, N_CALLS)


# -- dramatiq: a real Worker thread pool processing real actor sends ---

dramatiq = pytest.importorskip("dramatiq")
pytest.importorskip("whytrail.integrations.dramatiq")

from dramatiq.brokers.stub import StubBroker  # noqa: E402
from dramatiq.worker import Worker  # noqa: E402

import whytrail.integrations.dramatiq as whytrail_dramatiq  # noqa: E402


def test_dramatiq_concurrent_actor_failures_do_not_cross_contaminate():
    broker = StubBroker()
    broker.emit_after("process_boot")
    dramatiq.set_broker(broker)

    logger = logging.getLogger("whytrail.dramatiq.test.concurrency")
    logger.setLevel(logging.ERROR)
    handler = _ListHandler()
    logger.addHandler(handler)
    whytrail_dramatiq.install(broker, log_locals=True, logger=logger)

    @dramatiq.actor(max_retries=0)
    def flaky(secret):
        raise ValueError("boom")

    # worker_threads=8: dramatiq's own Worker already runs actors across
    # a real thread pool -- unlike RQ's SimpleWorker, this is genuine
    # concurrency, not a simulation of it.
    worker = Worker(broker, worker_timeout=100, worker_threads=8)
    worker.start()
    try:
        for i in range(N_CALLS):
            flaky.send(_secret_for(i))
        # fail_fast=False: the single-value test in test_dramatiq_plugin.py
        # uses fail_fast=True specifically because it only sends one
        # message and wants join() to raise as soon as that one fails.
        # Here every one of N_CALLS messages is expected to fail, and
        # fail_fast=True would stop waiting after the first -- leaving
        # the rest unprocessed and the assertion below vacuously wrong
        # about "no data missing."
        broker.join(flaky.queue_name, fail_fast=False)
        worker.join()
    finally:
        worker.stop()

    _assert_no_cross_contamination(handler.records, N_CALLS)


# -- RQ: whytrail's own installed handler, called concurrently directly -

fakeredis = pytest.importorskip("fakeredis")
rq = pytest.importorskip("rq")
pytest.importorskip("whytrail.integrations.rq")

import whytrail.integrations.rq as whytrail_rq  # noqa: E402


class _StubWorker:
    """Just enough of RQ's Worker interface for install() to attach its
    handler -- the handler itself (whytrail's own code, the only thing
    with any shared-state risk) is what this test actually exercises,
    not RQ's own job-dispatch machinery (already covered end to end by
    test_rq_plugin.py against a real SimpleWorker)."""

    def __init__(self):
        self.handlers: list = []

    def push_exc_handler(self, fn):
        self.handlers.append(fn)


def test_rq_installed_handler_concurrent_calls_do_not_cross_contaminate():
    logger = logging.getLogger("whytrail.rq.test.concurrency")
    logger.setLevel(logging.ERROR)
    handler = _ListHandler()
    logger.addHandler(handler)

    stub_worker = _StubWorker()
    whytrail_rq.install(stub_worker, log_locals=True, logger=logger)
    on_job_failure = stub_worker.handlers[0]

    def _fire(i: int) -> None:
        job = SimpleNamespace(func_name="flaky_task", args=(_secret_for(i),), kwargs={}, id=f"job-{i}")
        try:
            raise ValueError(f"job {i} failed")
        except ValueError as exc:
            on_job_failure(job, ValueError, exc, None)

    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(_fire, range(N_CALLS)))

    _assert_no_cross_contamination(handler.records, N_CALLS)
