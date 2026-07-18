"""loguru integration (ADR 0003, hook-based -- see
docs/plugin-guide.md's "other shape").

`logger.patch()`, not a sink -- patching lets the explanation reach
whichever sink(s) a user already has configured (file, stderr, a
remote service) instead of requiring them to replace their own sink
with ours, the same "don't fight the library's own extension point"
reasoning `pytest_plugin.py`'s module docstring gives for using
`report.sections` over patching `longrepr`.

`record["exception"]` is loguru's own structured exception info
(`.type`/`.value`/`.traceback`, `None` when there isn't one) -- no
`sys.exc_info()` fallback needed the way stdlib `logging`/`structlog`
need one, since loguru always resolves it eagerly onto the record.
"""

from __future__ import annotations

import typing as t

import loguru

import whytrail


def install(*, log_locals: bool = False) -> "loguru.Logger":
    """Returns a loguru logger patched to append a why() explanation
    to any message carrying exception info:

        from whytrail.integrations import loguru as whytrail_loguru

        logger = whytrail_loguru.install()
        ...
        try:
            ...
        except Exception:
            logger.exception("request failed")  # message gains a whytrail explanation

    Reassign the module-level `logger` your code already imports from
    `loguru`, or use the returned one directly -- both are the same
    kind of object loguru itself hands back from `logger.patch()`.

    `log_locals` defaults to False -- locals are redacted unless
    explicitly opted in, matching the parameter name and posture every
    other integration in this package uses. A first version of this
    function used `redact: bool = True` -- a different name and
    inverted polarity for the same concept, found auditing the whole
    ecosystem for naming consistency before 1.0.
    """

    def _patch(record: "loguru.Record") -> None:
        exc = record["exception"]
        if exc is None or exc.value is None:
            return
        explanation = whytrail.why(exc.value)
        if explanation.known:
            text = explanation.text if log_locals else explanation.redacted().text
            record["message"] = f"{record['message']}\n{text}"

    return loguru.logger.patch(t.cast("t.Callable[[t.Any], None]", _patch))
