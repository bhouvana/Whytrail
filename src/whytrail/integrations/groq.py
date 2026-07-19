"""whytrail plugin for the Groq SDK (ADR 0003).

`APIStatusError` (covering `RateLimitError`, `AuthenticationError`,
`NotFoundError`, `BadRequestError`, ...) carries the HTTP status and
the API's own structured error body -- the SDK is explicitly modeled
after openai's, so this mirrors `whytrail[openai]` exactly, the same
way `whytrail[cohere]`/`whytrail[mistralai]` do for their own
near-identical shapes.

The error body goes through `locals`, not `description` (ADR 0002 §3
item 5): a content-policy or validation error's body can echo back the
prompt that triggered it.
"""

from __future__ import annotations

import groq

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_status_error(exc: "groq.APIStatusError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    body_locals = {"body": repr(exc.body)} if exc.body is not None else None
    if body_locals:
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=body_locals,
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def _explain_connection_error(exc: "groq.APIConnectionError") -> Explanation:
    subject = f"{type(exc).__name__}: {exc}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(groq.APIStatusError, _explain_status_error)
    register_from_plugin(groq.APIConnectionError, _explain_connection_error)
