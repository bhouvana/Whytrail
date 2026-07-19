"""whytrail plugin for notion-client (ADR 0003).

`HTTPResponseError` (covering the more specific `APIResponseError`)
carries Notion's own documented error `.code`, HTTP `.status`,
`.headers`, `.request_id`, and `.additional_data` -- detail a bare
`str(exc)` (just the message) drops entirely.

`.body`/`.additional_data` go through `locals`, not `description`
(ADR 0002 §3 item 5): they can reference the specific page, database,
or block ID involved.
"""

from __future__ import annotations

import notion_client.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_http_response_error(exc: "notion_client.errors.HTTPResponseError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status} ({exc.code})"
    locals_ = {"body": exc.body}
    if exc.additional_data:
        locals_["additional_data"] = repr(exc.additional_data)
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals=locals_,
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(notion_client.errors.HTTPResponseError, _explain_http_response_error)
