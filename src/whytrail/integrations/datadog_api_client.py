"""whytrail plugin for datadog-api-client, Datadog's own REST
management API client (ADR 0003).

Distinct from `whytrail[ddtrace]`, already bundled: that's the APM
tracer (a hook-based integration attaching explanations to spans),
this is a separate, unrelated OpenAPI-generated client for Datadog's
own management API (dashboards, monitors, metrics). `ApiException`
carries the HTTP status, reason, response body, and headers -- the
same generated-client shape as `whytrail[pinecone]`/`whytrail[plaid]`.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): it can reference the specific dashboard, monitor, or
metric name involved.
"""

from __future__ import annotations

import datadog_api_client.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "datadog_api_client.exceptions.ApiException") -> Explanation:
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
    register_from_plugin(datadog_api_client.exceptions.ApiException, _explain_api_exception)
