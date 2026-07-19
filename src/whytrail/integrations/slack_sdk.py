"""whytrail plugin for the Slack SDK (ADR 0003).

`SlackApiError` carries the full `SlackResponse` -- HTTP status code,
the API URL called, and Slack's own structured `data` dict (an
`error` code, plus `needed`/`provided` for scope errors) -- detail
`str(exc)` folds into one line prefixed with a fixed message.

`response.data` goes through `locals`, not `description` (ADR 0002 §3
item 5): it's the raw API response, which can include a channel name,
user ID, or message text depending on which call failed.
"""

from __future__ import annotations

import slack_sdk.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "slack_sdk.errors.SlackApiError") -> Explanation:
    response = exc.response
    status_code = getattr(response, "status_code", None)
    error_code = None
    if hasattr(response, "get"):
        error_code = response.get("error")
    subject = f"{type(exc).__name__}: HTTP {status_code}" + (f" ({error_code})" if error_code else "")
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description="response detail",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"data": repr(getattr(response, "data", response))},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(slack_sdk.errors.SlackApiError, _explain_api_error)
