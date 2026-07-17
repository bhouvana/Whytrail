"""whytrail plugin for pyzmq (ADR 0003).

`zmq.ZMQError` carries `.errno` (a real POSIX/ZeroMQ errno code) and
`.strerror` -- confirmed directly, not assumed: `str(exc)` renders
*only* `.strerror` (e.g. `"Unknown error"` for an unmapped code),
dropping the numeric errno entirely, so a bare traceback doesn't even
show which error this actually was, let alone let a caller branch on
it.

No redaction concern here: both fields are OS/protocol-level error
codes, never request content, so nothing needs to route through
`locals`.
"""

from __future__ import annotations

import zmq

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_zmq_error(exc: "zmq.ZMQError") -> Explanation:
    subject = f"{type(exc).__name__} (errno {exc.errno}): {exc.strerror}"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(zmq.ZMQError, _explain_zmq_error)
