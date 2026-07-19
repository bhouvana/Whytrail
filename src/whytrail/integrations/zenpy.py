"""whytrail plugin for zenpy, the Zendesk SDK (ADR 0003).

`APIException` carries the real `requests.Response` object Zendesk's
API returned (`.response`) -- a bare `str(exc)` shows whatever message
zenpy chose to pass, not the response's own status/body.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): a Zendesk API error body can reference the specific
ticket, user, or organization involved.
"""

from __future__ import annotations

import zenpy.lib.exception

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "zenpy.lib.exception.APIException") -> Explanation:
    response = exc.response
    status_code = getattr(response, "status_code", None)
    subject = f"{type(exc).__name__}: HTTP {status_code}" if status_code is not None else type(exc).__name__
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    if response is not None:
        body = getattr(response, "text", None)
        if body:
            steps.append(
                ExplanationStep(
                    description="response body",
                    confidence=Confidence.EXPLICIT.value,
                    kind="external",
                    locals={"body": body},
                )
            )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(zenpy.lib.exception.APIException, _explain_api_exception)
