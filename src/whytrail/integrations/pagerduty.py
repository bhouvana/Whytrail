"""whytrail plugin for the pagerduty SDK (ADR 0003).

Found while triaging this ecosystem's candidates: the deprecated
`pdpyras` package (deprecated 2025-06-20) was the original candidate,
replaced here by its official successor, `pagerduty`, which carries the
same structured shape -- `HttpError` guarantees a real `.response`
(unlike the base `Error`, whose `.response` can be `None` for a network
failure), from which the HTTP status is read.

`.msg`/response body go through `locals`, not `description` (ADR 0002
§3 item 5): a PagerDuty API error body can reference the specific
incident, service, or escalation policy involved.
"""

from __future__ import annotations

import pagerduty

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_http_error(exc: "pagerduty.HttpError") -> Explanation:
    status_code = getattr(exc.response, "status_code", None)
    subject = f"{type(exc).__name__}: HTTP {status_code}" if status_code is not None else type(exc).__name__
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"msg": exc.msg},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pagerduty.HttpError, _explain_http_error)
