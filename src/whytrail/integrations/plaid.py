"""whytrail plugin for the Plaid SDK (ADR 0003).

`plaid.exceptions.ApiException` (the base of `NotFoundException`,
`UnauthorizedException`, `ForbiddenException`, ...) carries the HTTP
status, reason, headers, and raw response body -- the same generated-
OpenAPI-client shape as `whytrail[pinecone]`.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): a Plaid error body routinely includes an `error_code`/
`error_message` pair that can reference the specific account or
institution involved.
"""

from __future__ import annotations

import plaid.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "plaid.exceptions.ApiException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status}" + (f" ({exc.reason})" if exc.reason else "")
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    if exc.body:
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
    register_from_plugin(plaid.exceptions.ApiException, _explain_api_exception)
