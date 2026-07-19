"""whytrail plugin for the Asana SDK (ADR 0003).

`ApiException` carries the HTTP status, reason, response body, and
headers -- the same generated-OpenAPI-client shape as
`whytrail[pinecone]`/`whytrail[plaid]`/`whytrail[okta]` in this
ecosystem.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): it can reference the specific task, project, or workspace
involved.
"""

from __future__ import annotations

import asana.rest

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "asana.rest.ApiException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status}" + (f" ({exc.reason})" if exc.reason else "")
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
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
    register_from_plugin(asana.rest.ApiException, _explain_api_exception)
