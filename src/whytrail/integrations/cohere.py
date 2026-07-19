"""whytrail plugin for the Cohere SDK (ADR 0003).

`ApiError` (covering `NotFoundError`, `UnauthorizedError`,
`TooManyRequestsError`, ...) carries the HTTP status code and the
API's own structured response body -- same shape as `whytrail[openai]`
and `whytrail[anthropic]`, registered the same way for the same reason.

Found while building this: `ApiError` isn't re-exported from
`cohere.errors` (its own subclasses' MRO shows it lives at
`cohere.core.api_error.ApiError`) -- confirmed by walking
`NotFoundError.__mro__` directly rather than assumed from `cohere.errors`'
public names.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): a validation or content-moderation error's body can echo
back the prompt that triggered it.
"""

from __future__ import annotations

import cohere.core.api_error

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "cohere.core.api_error.ApiError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    if exc.body is not None:
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"body": repr(exc.body)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(cohere.core.api_error.ApiError, _explain_api_error)
