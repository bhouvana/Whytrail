"""whytrail plugin for the elasticsearch-py client (ADR 0003).

`elasticsearch.ApiError` (covering `NotFoundError`, `ConflictError`,
`AuthorizationException`, etc., all subclasses of
`elastic_transport.ApiError`) carries the HTTP status
(`.meta.status`), the raw structured error body Elasticsearch itself
returned (`.body`, typically `{"error": {"type": ..., "reason": ...,
"index": ...}, "status": ...}`), and any nested bulk-request errors
(`.errors`) -- all of it collapsed by `str(exc)` into a one-line
`[404] index_not_found_exception` that drops the actual reason and
which index/resource was involved.

The full `.body` goes through `locals`, not `description` (ADR 0002
§3 item 5): `error.reason` in particular can echo back a raw query
fragment (a `parsing_exception`'s reason routinely quotes the
offending query text verbatim), so nothing from inside the body is
safe to put in a field that isn't stripped by `.redacted()`. Only the
HTTP status -- structural metadata, never request content -- is safe
in `description`.
"""

from __future__ import annotations

import elasticsearch

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "elasticsearch.ApiError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc.message}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    status = getattr(exc.meta, "status", None) if exc.meta else None
    body_locals = {"body": repr(exc.body)} if exc.body is not None else None
    if status or body_locals:
        steps.append(
            ExplanationStep(
                description=f"status={status}" if status else "response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=body_locals,
            )
        )
    subject = f"{type(exc).__name__}: {exc.message}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(elasticsearch.ApiError, _explain_api_error)
