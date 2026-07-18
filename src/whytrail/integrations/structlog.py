"""structlog integration (ADR 0003, hook-based -- see
docs/plugin-guide.md's "other shape").

A processor, not a Filter (stdlib `logging`'s shape) -- structlog's
own extension point is a processor chain operating on a structured
`event_dict`, so the idiomatic addition is a structured `why` key
(`explanation.json()`), not text spliced into the message the way the
stdlib integration does. Must run *before* structlog's own
`format_exc_info`/`dict_tracebacks` processors in the chain: those
consume and remove `exc_info` from the event_dict once they've
rendered it, so this processor needs to see it first.

`exc_info` in the event_dict is `True` (meaning "use sys.exc_info()"),
an exception instance, or a `(type, value, traceback)` tuple depending
on how the call site passed it (`log.exception(...)`,
`log.error(..., exc_info=some_exc)`, etc.) -- all three resolved here,
matching what structlog's own processors already handle.
"""

from __future__ import annotations

import sys
import typing as t

import structlog  # noqa: F401 -- unused directly (this processor is pure event_dict manipulation), imported so a missing dependency fails at import time the way every other integration's availability check expects

import whytrail


def add_whytrail_explanation(
    log_locals: bool = False,
) -> t.Callable[[t.Any, str, dict[str, t.Any]], dict[str, t.Any]]:
    """Returns a structlog processor. Add it to `processors=[...]`
    *before* `format_exc_info`/`dict_tracebacks`:

        import structlog
        from whytrail.integrations import structlog as whytrail_structlog

        structlog.configure(
            processors=[
                whytrail_structlog.add_whytrail_explanation(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ]
        )

    `log_locals` defaults to False -- locals are redacted unless
    explicitly opted in, matching the parameter name and posture every
    other integration in this package uses (`celery.install(log_locals=...)`,
    the stdlib `logging` integration, fastapi/flask/django's own
    `log_locals` opt-in). A first version of this function used
    `redact: bool = True` -- a different name and inverted polarity for
    the same concept, found auditing the whole ecosystem for naming
    consistency before 1.0.
    """

    def processor(logger: t.Any, method_name: str, event_dict: dict[str, t.Any]) -> dict[str, t.Any]:
        exc = _exception_from(event_dict)
        if exc is not None:
            explanation = whytrail.why(exc)
            if explanation.known:
                event_dict["why"] = (explanation if log_locals else explanation.redacted()).json()
        return event_dict

    return processor


def _exception_from(event_dict: dict[str, t.Any]) -> BaseException | None:
    exc_info = event_dict.get("exc_info")
    if exc_info is True:
        return sys.exc_info()[1]
    if isinstance(exc_info, BaseException):
        return exc_info
    if isinstance(exc_info, tuple) and len(exc_info) == 3:
        value = exc_info[1]
        return value if isinstance(value, BaseException) else None
    return None
