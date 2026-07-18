"""stdlib `logging` integration (ADR 0003, hook-based -- see
docs/plugin-guide.md's "other shape").

A `logging.Filter`, not a Handler or Formatter: a Filter runs for
every handler attached to the logger it's installed on and can mutate
the record before formatting, so `install()` on the root logger makes
every existing handler (console, file, a log aggregator's own handler)
pick up the explanation automatically -- no per-handler wiring, no
custom Formatter subclass a team's existing logging config would need
to adopt.

Only fires for records carrying real exception info (`exc_info` set,
the normal shape of `logger.exception(...)` or `logger.error(...,
exc_info=True)`) -- a plain `logger.info("...")` call is completely
unaffected, matching the same "off unless there's something to
explain" posture every other integration in this package follows.
"""

from __future__ import annotations

import logging

import whytrail


class WhytrailFilter(logging.Filter):
    """Appends a why() explanation to any log record with exception
    info attached. `log_locals` defaults to False -- locals are
    redacted unless explicitly opted in, the same parameter name and
    posture every other integration in this package uses
    (`celery.install(log_locals=...)`, `dramatiq.install(log_locals=...)`,
    `rq.install(log_locals=...)`, the `log_locals` half of
    fastapi/flask/django's two-opt-in design) -- a first version of
    this module used `redact: bool = True` instead, a different name
    *and* inverted polarity for the same concept, found and fixed
    auditing the whole ecosystem for naming consistency before 1.0,
    not caught when this module was first written in isolation.
    """

    def __init__(self, *, log_locals: bool = False) -> None:
        super().__init__()
        self.log_locals = log_locals

    def filter(self, record: logging.LogRecord) -> bool:
        exc = _exception_from(record)
        if exc is not None:
            explanation = whytrail.why(exc)
            if explanation.known:
                text = explanation.text if self.log_locals else explanation.redacted().text
                record.msg = f"{record.getMessage()}\n{text}"
                record.args = ()
        return True


def install(logger: logging.Logger | None = None, *, log_locals: bool = False) -> WhytrailFilter:
    """Attach a WhytrailFilter to `logger` (default: the root logger,
    so every logger that propagates to it is covered).

        import logging
        from whytrail.integrations import logging as whytrail_logging

        whytrail_logging.install()  # root logger, locals redacted by default
        ...
        try:
            ...
        except Exception:
            logging.exception("request failed")  # gains a whytrail explanation automatically

    Returns the installed filter so it can be removed later via
    `logger.removeFilter(...)` if needed.
    """
    target = logger if logger is not None else logging.getLogger()
    filt = WhytrailFilter(log_locals=log_locals)
    target.addFilter(filt)
    return filt


def _exception_from(record: logging.LogRecord) -> BaseException | None:
    exc_info = record.exc_info
    if not exc_info:
        return None
    if isinstance(exc_info, tuple):
        return exc_info[1]
    return None
