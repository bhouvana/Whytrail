"""Celery integration (ADR 0002 §7, Tier B).

Connects to Celery's `task_failure` signal and logs a whytrail
explanation alongside the task's args/kwargs -- most useful exactly
where Celery's own default logging is weakest: a task that failed on
a retry, where the traceback shows the exception but not which
attempt's arguments actually caused it.

Task args/kwargs go through the same locals-style redaction as
everything else in this ecosystem (ADR 0002 §3 item 5): a task payload
is exactly the kind of thing that can carry a customer record or a
token, so it's attached via ExplanationStep.locals and redacted by
default, not logged raw just because it came from a queue instead of
a stack frame.
"""

from __future__ import annotations

import logging
import typing as t

from celery.signals import task_failure

import whytrail
from whytrail import Confidence, ExplanationStep

_logger = logging.getLogger("whytrail.celery")


def install(*, log_locals: bool = False, logger: logging.Logger | None = None) -> None:
    """Connect whytrail's task_failure handler.

        from whytrail.integrations import celery
        celery.install()

    `log_locals` defaults to False -- task args/kwargs are logged
    redacted unless explicitly opted in, the same posture as every
    other integration here.
    """
    log = logger or _logger

    # Celery's own stub types signal.connect() loosely enough that mypy
    # --strict considers anything it wraps "untyped" regardless of this
    # function's own annotations -- a third-party stub limitation, not
    # a gap in whytrail's own typing, silenced on the line below.
    @task_failure.connect(weak=False)  # type: ignore[untyped-decorator]
    def _on_task_failure(  # noqa: ANN001 - Celery's signal signature
        sender: t.Any = None,
        task_id: t.Any = None,
        exception: BaseException | None = None,
        args: t.Any = None,
        kwargs: t.Any = None,
        traceback: t.Any = None,
        einfo: t.Any = None,
        **extra: t.Any,
    ) -> None:
        if exception is None:
            return
        explanation = whytrail.why(exception)
        if explanation.known:
            explanation.steps.append(
                ExplanationStep(
                    description=f"task {getattr(sender, 'name', sender)!r} invoked with these arguments",
                    confidence=Confidence.EXPLICIT.value,
                    kind="call",
                    locals=_args_as_dict(args, kwargs),
                )
            )
        log_explanation = explanation if log_locals else explanation.redacted()
        log.error(
            "task %s (id=%s) failed\n%s",
            getattr(sender, "name", sender),
            task_id,
            log_explanation.text,
        )


def _args_as_dict(args: t.Any, kwargs: t.Any) -> dict[str, str] | None:
    result: dict[str, str] = {}
    for i, value in enumerate(args or ()):
        result[f"args[{i}]"] = repr(value)
    for key, value in (kwargs or {}).items():
        result[f"kwargs[{key}]"] = repr(value)
    return result or None
