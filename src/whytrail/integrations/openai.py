"""whytrail plugin for the openai SDK (ADR 0003).

`APIStatusError` (covering `RateLimitError`, `AuthenticationError`,
`NotFoundError`, `BadRequestError`, ...) already carries the HTTP
status, request ID, and the API's own structured error body -- detail
`str(exc)` collapses into one line.

The error body goes through `locals`, not `description`, deliberately
(ADR 0002 §3 item 5): a content-policy or validation error's body can
echo back the request content that triggered it -- which may be a
user's prompt, and is exactly the kind of thing that shouldn't cross a
process boundary unredacted by default.
"""

from __future__ import annotations


import openai

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_status_error(exc: "openai.APIStatusError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: HTTP {exc.status_code}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    detail_parts = []
    code = getattr(exc, "code", None)
    err_type = getattr(exc, "type", None)
    if code:
        detail_parts.append(f"code={code}")
    if err_type:
        detail_parts.append(f"type={err_type}")
    if exc.request_id:
        detail_parts.append(f"request_id={exc.request_id}")
    body_locals = {"body": repr(exc.body)} if exc.body is not None else None
    if detail_parts or body_locals:
        steps.append(
            ExplanationStep(
                description=", ".join(detail_parts) if detail_parts else "response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=body_locals,
            )
        )
    return Explanation(subject=f"{type(exc).__name__}: HTTP {exc.status_code}", steps=steps, tracked=True)


def _explain_connection_error(exc: "openai.APIConnectionError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}", confidence=Confidence.EXPLICIT.value, kind="external"
        )
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(openai.APIStatusError, _explain_status_error)
    register_from_plugin(openai.APIConnectionError, _explain_connection_error)
