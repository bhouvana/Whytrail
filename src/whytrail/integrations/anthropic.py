"""whytrail plugin for the anthropic SDK (ADR 0003).

Same shape as whytrail-openai, for the same reason: `APIStatusError`
(covering `RateLimitError`, `AuthenticationError`, `BadRequestError`,
`OverloadedError`, ...) carries the HTTP status, request ID, and the
API's own structured error body, which `str(exc)` collapses into one
line. The body goes through `locals`, not `description`, for the same
reason as whytrail-openai's: it can echo back request content.
"""

from __future__ import annotations


import anthropic

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_status_error(exc: "anthropic.APIStatusError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: HTTP {exc.status_code}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    detail_parts = []
    if exc.request_id:
        detail_parts.append(f"request_id={exc.request_id}")
    body = getattr(exc, "body", None)
    if isinstance(body, dict) and body.get("type"):
        detail_parts.append(f"type={body['type']}")
    body_locals = {"body": repr(body)} if body is not None else None
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


def _explain_connection_error(exc: "anthropic.APIConnectionError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}", confidence=Confidence.EXPLICIT.value, kind="external"
        )
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(anthropic.APIStatusError, _explain_status_error)
    register_from_plugin(anthropic.APIConnectionError, _explain_connection_error)
