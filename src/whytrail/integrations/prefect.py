"""whytrail plugin for Prefect (ADR 0003).

Registers a state-change hook (`on_failure=[...]` on a `@task`/
`@flow`) that logs a whytrail explanation. Same intent as
whytrail-celery/whytrail-rq/whytrail-dramatiq, adapted to Prefect's hook
protocol -- but deliberately does not capture task
arguments/parameters the way those three do: `TaskRun` (the object
Prefect's own hook signature passes) doesn't expose bound parameters
directly, only through Prefect's API client, and fetching them would
mean this plugin making a network call inside a failure handler. Left
out rather than built on a shakier foundation -- see the module's own
test suite for what's actually verified.

The underlying exception is recovered via `state.result()`, which
Prefect's own `State` API re-raises from -- the documented way to get
at it, not an internal API.
"""

from __future__ import annotations

import logging
import typing as t

import whytrail

_logger = logging.getLogger("whytrail.prefect")


def on_failure_hook(logger: logging.Logger | None = None) -> t.Callable[[t.Any, t.Any, t.Any], None]:
    """Returns a hook usable directly in `on_failure=[...]`.

        from whytrail.integrations.prefect import on_failure_hook

        @task(on_failure=[on_failure_hook()], retries=0)
        def my_task(...): ...
    """
    log = logger or _logger

    def _hook(task_or_flow: t.Any, run: t.Any, state: t.Any) -> None:
        try:
            state.result()
        except BaseException as exc:  # noqa: BLE001 - this *is* the failure being explained
            explanation = whytrail.why(exc)
            log.error(
                "%s %r (run_id=%s) failed\n%s",
                type(task_or_flow).__name__.lower(),
                getattr(task_or_flow, "name", task_or_flow),
                getattr(run, "id", "?"),
                explanation.text,
            )

    return _hook
