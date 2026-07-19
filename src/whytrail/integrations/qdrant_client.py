"""whytrail plugin for the Qdrant client SDK (ADR 0003).

`UnexpectedResponse` carries the HTTP status code, reason phrase, and
the raw response body (with a `.structured()` helper to parse it as
JSON) -- detail `str(exc)` truncates to a fixed-length preview.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): it's the collection/point payload Qdrant echoes back on a
validation error.
"""

from __future__ import annotations

import typing as t

from qdrant_client.http.exceptions import UnexpectedResponse

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_unexpected_response(exc: "UnexpectedResponse") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code} {exc.reason_phrase}".strip()
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    if exc.content:
        body: t.Any
        try:
            body = exc.structured()
        except Exception:  # noqa: BLE001 - content isn't valid JSON, fall back to raw bytes
            body = exc.content
        steps.append(
            ExplanationStep(
                description="response content",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"content": repr(body)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(UnexpectedResponse, _explain_unexpected_response)
