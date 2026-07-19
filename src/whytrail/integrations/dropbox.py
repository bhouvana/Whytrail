"""whytrail plugin for the Dropbox SDK (ADR 0003).

`ApiError` carries a `.request_id` (shareable with Dropbox Support to
pinpoint the exact failed request) and `.error` -- the route-specific,
strongly-typed error data Dropbox's Stone-generated API returns per
endpoint (e.g. a `ListFolderError` union telling you exactly which
variant occurred: path not found, malformed path, ...), which a bare
`str(exc)` only shows via `repr()`.

`.error`/`.user_message_text` go through `locals`, not `description`
(ADR 0002 §3 item 5): the route-specific error data routinely embeds
the actual file/folder path that caused the failure.
"""

from __future__ import annotations

import dropbox.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "dropbox.exceptions.ApiError") -> Explanation:
    subject = f"{type(exc).__name__}: request_id={exc.request_id}"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"error": repr(exc.error)},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(dropbox.exceptions.ApiError, _explain_api_error)
