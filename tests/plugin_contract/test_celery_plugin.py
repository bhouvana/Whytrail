"""Validates whytrail-celery against Celery's real task_failure signal
(fired directly, no broker/worker needed -- the standard way to test
Celery signal handlers in isolation)."""

from __future__ import annotations

import logging

import pytest

celery = pytest.importorskip("celery")
pytest.importorskip("whytrail.integrations.celery")

import whytrail.integrations.celery as whytrail_celery  # noqa: E402
from celery import Celery  # noqa: E402
from celery.signals import task_failure  # noqa: E402

SECRET = "sk-super-secret-token"


@pytest.fixture(scope="module")
def app():
    return Celery("whytrail-celery-tests", broker="memory://", backend="cache+memory://")


@pytest.fixture(scope="module")
def flaky_task(app):
    @app.task(name="whytrail_tests.flaky")
    def flaky(customer_email):
        raise ValueError("boom")

    return flaky


@pytest.fixture(autouse=True)
def _install_once():
    # install() connects a signal receiver; connecting twice would
    # double-log, so guard with a module-level flag rather than
    # calling install() fresh in every test.
    if not getattr(_install_once, "_done", False):
        whytrail_celery.install()
        _install_once._done = True


def _fire_failure(sender, args=(SECRET,), kwargs=None):
    task_failure.send(
        sender=sender,
        task_id="test-task-id",
        exception=ValueError("boom"),
        args=list(args),
        kwargs=kwargs or {},
        traceback=None,
        einfo=None,
    )


def test_logs_explanation_on_task_failure(flaky_task, caplog):
    with caplog.at_level(logging.ERROR, logger="whytrail.celery"):
        _fire_failure(flaky_task)
    assert "boom" in caplog.text
    assert "failed" in caplog.text


def test_args_are_redacted_by_default(flaky_task, caplog):
    with caplog.at_level(logging.ERROR, logger="whytrail.celery"):
        _fire_failure(flaky_task)
    assert SECRET not in caplog.text


def test_none_exception_is_ignored(flaky_task, caplog):
    with caplog.at_level(logging.ERROR, logger="whytrail.celery"):
        task_failure.send(
            sender=flaky_task, task_id="x", exception=None, args=[], kwargs={}, traceback=None, einfo=None
        )
    assert "failed" not in caplog.text
