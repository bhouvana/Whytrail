"""whytrail plugin for RQ / Redis Queue (ADR 0003).

Connects to a Worker's exception-handler chain (`Worker.
push_exc_handler`) and logs a whytrail explanation -- including the
job's args/kwargs -- alongside the raised exception. Same shape as
whytrail-celery, adapted to RQ's handler-chain protocol instead of a
signal: this handler always returns True so RQ's own default handler
(moving the job to the failed queue) still runs afterward -- this
plugin observes, it doesn't take over failure handling.

Job args/kwargs go through the same locals-style redaction as
everywhere else in this ecosystem (ADR 0002 §3 item 5): a job payload
is exactly the kind of thing that can carry a customer record or a
token.
"""

from __future__ import annotations

import logging
import typing as t

import whytrail
from whytrail import Confidence, ExplanationStep

_logger = logging.getLogger("whytrail.rq")


def install(worker: t.Any, *, log_locals: bool = False, logger: logging.Logger | None = None) -> None:
    """Attach to a Worker's exception-handler chain.

        from rq import Worker
        from whytrail.integrations import rq as whytrail_rq

        worker = Worker(["default"], connection=redis_conn)
        whytrail_rq.install(worker)
        worker.work()
    """
    log = logger or _logger

    def _on_job_failure(job: t.Any, exc_type: type, exc_value: BaseException, traceback: t.Any) -> bool:
        explanation = whytrail.why(exc_value)
        if explanation.known:
            explanation.steps.append(
                ExplanationStep(
                    description=f"job {job.func_name!r} invoked with these arguments",
                    confidence=Confidence.EXPLICIT.value,
                    kind="call",
                    locals=_args_as_dict(job.args, job.kwargs),
                )
            )
        log_explanation = explanation if log_locals else explanation.redacted()
        log.error("job %s (id=%s) failed\n%s", job.func_name, job.id, log_explanation.text)
        return True  # let RQ's own default handler (failed queue) still run

    worker.push_exc_handler(_on_job_failure)


def _args_as_dict(args: t.Any, kwargs: t.Any) -> dict[str, str] | None:
    result: dict[str, str] = {}
    for i, value in enumerate(args or ()):
        result[f"args[{i}]"] = repr(value)
    for key, value in (kwargs or {}).items():
        result[f"kwargs[{key}]"] = repr(value)
    return result or None
