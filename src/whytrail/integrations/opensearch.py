"""whytrail plugin for opensearch-py (ADR 0003).

`opensearchpy.exceptions.TransportError` (covering `NotFoundError`,
`ConflictError`, `RequestError`, ...) carries the HTTP status
(`.status_code`), a short error type (`.error`), and the full
structured response body (`.info`, typically `{"error": {"type": ...,
"reason": ..., "index": ...}, "status": ...}`) -- collapsed by
`str(exc)` into `NotFoundError(404, 'index_not_found_exception')`,
dropping `.info`'s actual `reason` and which index/resource was
involved entirely. `.status_code`/`.error`/`.info` are properties, not
`__dict__` entries (`vars(exc)` is empty), so this reads them via
normal attribute access, the same gotcha already found in
`whytrail-pika`.

The full `.info` goes through `locals`, not `description` (ADR 0002
§3 item 5), the same posture as `whytrail-elasticsearch` (opensearch-py
is a fork of elasticsearch-py and shares the same response shape):
`error.reason` routinely echoes back the offending query or resource
name. Only `.status_code`/`.error` -- structural metadata, never
request content -- are safe in `description`.
"""

from __future__ import annotations

import opensearchpy.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_transport_error(exc: "opensearchpy.exceptions.TransportError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc.error}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    status = getattr(exc, "status_code", None)
    info = getattr(exc, "info", None)
    info_locals = {"info": repr(info)} if info else None
    if status is not None or info_locals:
        steps.append(
            ExplanationStep(
                description=f"status_code={status}" if status is not None else "response info",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=info_locals,
            )
        )
    subject = f"{type(exc).__name__}: {status} {exc.error}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(opensearchpy.exceptions.TransportError, _explain_transport_error)
