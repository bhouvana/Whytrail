"""Validates whytrail-prefect against a real Prefect flow/task run
executed through Prefect's own ephemeral local server (auto-started,
no manual setup) -- a real on_failure hook firing from a real failed
task, not a hand-constructed event."""

from __future__ import annotations

import logging

import pytest

prefect = pytest.importorskip("prefect")
pytest.importorskip("whytrail.integrations.prefect")

from prefect import flow, task  # noqa: E402

from whytrail.integrations.prefect import on_failure_hook  # noqa: E402


class _ListHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.records: list[str] = []

    def emit(self, record):
        self.records.append(self.format(record))


def test_task_failure_is_logged_with_explanation():
    logger = logging.getLogger("whytrail.prefect.test")
    logger.setLevel(logging.ERROR)
    handler = _ListHandler()
    logger.addHandler(handler)

    @task(on_failure=[on_failure_hook(logger=logger)], retries=0)
    def flaky():
        raise ValueError("boom")

    @flow
    def my_flow():
        flaky()

    with pytest.raises(ValueError):
        my_flow()

    logger.removeHandler(handler)
    log_text = "\n".join(handler.records)
    assert "boom" in log_text
    assert "flaky" in log_text
