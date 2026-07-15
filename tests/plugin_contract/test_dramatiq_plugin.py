"""Validates whytrail-dramatiq against a real dramatiq StubBroker +
Worker processing a real failing actor -- no real message broker
needed, StubBroker is dramatiq's own recommended choice for tests."""

from __future__ import annotations

import logging

import pytest

dramatiq = pytest.importorskip("dramatiq")
pytest.importorskip("whytrail_dramatiq")

from dramatiq.brokers.stub import StubBroker  # noqa: E402
from dramatiq.worker import Worker  # noqa: E402

import whytrail_dramatiq  # noqa: E402

SECRET = "sk-super-secret-token"


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(self.format(record))


def _run_actor(arg, *, log_locals=False):
    broker = StubBroker()
    broker.emit_after("process_boot")
    dramatiq.set_broker(broker)

    logger = logging.getLogger(f"whytrail.dramatiq.test.{id(broker)}")
    logger.setLevel(logging.ERROR)
    handler = _ListHandler()
    logger.addHandler(handler)
    whytrail_dramatiq.install(broker, log_locals=log_locals, logger=logger)

    @dramatiq.actor(max_retries=0)
    def flaky(x):
        raise ValueError("boom")

    worker = Worker(broker, worker_timeout=100)
    worker.start()
    try:
        flaky.send(arg)
        with pytest.raises(Exception):
            broker.join(flaky.queue_name, fail_fast=True)
        worker.join()
    finally:
        worker.stop()

    return "\n".join(handler.records)


def test_actor_failure_is_logged():
    log_text = _run_actor("some value")
    assert "ValueError: boom" in log_text
    assert "flaky" in log_text


def test_args_are_redacted_by_default():
    log_text = _run_actor(SECRET)
    assert SECRET not in log_text


def test_log_locals_true_includes_args():
    log_text = _run_actor(SECRET, log_locals=True)
    assert SECRET in log_text
