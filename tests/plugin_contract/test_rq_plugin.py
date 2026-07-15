"""Validates whytrail-rq against a real RQ SimpleWorker processing a
real job from a fakeredis-backed queue -- no actual Redis server, but
a real enqueue -> worker.work() -> exception-handler-chain round trip,
not a hand-constructed event.

Uses SimpleWorker rather than the default Worker: RQ's default Worker
forks a subprocess per job (os.fork()), which doesn't exist on
Windows and isn't appropriate for a test process anyway; SimpleWorker
(in-process execution) is RQ's own recommended choice for tests.

Uses an explicit `logger=` (with a list-capturing handler) rather than
pytest's `caplog` fixture: RQ's own Worker reconfigures logging during
`work()` in a way that detaches caplog's root-logger handler, so
caplog silently sees nothing even though the log call really happens
(confirmed by hand against real stdout before writing this test).
install()'s `logger` parameter exists for dependency injection in
exactly this kind of situation.

RQ requires task functions to be importable by module path (not
defined inline or in __main__), which is exactly what a pytest test
module already is -- flaky_task below is a real, importable function.
"""

from __future__ import annotations

import logging

import pytest

fakeredis = pytest.importorskip("fakeredis")
rq = pytest.importorskip("rq")
pytest.importorskip("whytrail.integrations.rq")

import whytrail.integrations.rq as whytrail_rq  # noqa: E402

SECRET = "sk-super-secret-token"


def flaky_task(x):
    # Deliberately does NOT interpolate x into the message: this
    # isolates "are the job's *arguments* redacted" (what these tests
    # check) from "does the exception's own message get redacted"
    # (it doesn't, anywhere in this codebase -- an exception's own
    # str() has always been treated as content being explained, not
    # as locals-style metadata; see explainers/builtin.py's tier 1).
    # An earlier version of this test used f"boom with {x}" and failed
    # confusingly for exactly that reason -- caught by running it, not
    # by reasoning about it in advance.
    raise ValueError("boom")


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(self.format(record))


def _run_job(*args, log_locals=False):
    conn = fakeredis.FakeStrictRedis()
    # NOT is_async=False: that executes the job synchronously at
    # enqueue() time, before the worker (and its exception handler
    # below) even exists, which silently made the worker have nothing
    # left to process -- caught by these tests failing, not assumed.
    queue = rq.Queue(connection=conn)
    job = queue.enqueue(flaky_task, *args)

    logger = logging.getLogger(f"whytrail.rq.test.{id(conn)}")
    logger.setLevel(logging.ERROR)
    handler = _ListHandler()
    logger.addHandler(handler)

    worker = rq.SimpleWorker([queue], connection=conn)
    whytrail_rq.install(worker, log_locals=log_locals, logger=logger)
    worker.work(burst=True)
    job.refresh()
    return job, "\n".join(handler.records)


def test_job_fails_and_is_logged():
    job, log_text = _run_job("some value")
    assert job.get_status() == "failed"
    assert "ValueError: boom" in log_text
    assert "flaky_task" in log_text


def test_args_are_redacted_by_default():
    _, log_text = _run_job(SECRET)
    assert SECRET not in log_text


def test_log_locals_true_includes_args():
    _, log_text = _run_job(SECRET, log_locals=True)
    assert SECRET in log_text


def test_rqs_own_failure_handling_still_runs():
    """install()'s handler always returns True so it doesn't take over
    failure handling -- confirm the job still ends up in RQ's own
    failed state, not silently swallowed."""
    job, _ = _run_job("x")
    assert job.get_status() == "failed"
