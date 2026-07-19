"""whytrail plugin for discord.py (ADR 0003).

`HTTPException` carries the HTTP status, Discord's own numeric API
error code, and the (already field-flattened) error text -- detail
`str(exc)` folds into one line ("{status} {reason} (error code:
{code}): {text}").

`.text` goes through `locals`, not `description` (ADR 0002 §3 item 5):
it can include per-field validation detail that echoes back the actual
message/embed content that was rejected.
"""

from __future__ import annotations

import discord.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_http_exception(exc: "discord.errors.HTTPException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status}" + (f" (Discord code {exc.code})" if exc.code else "")
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    if exc.text:
        steps.append(
            ExplanationStep(
                description="response detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"text": exc.text},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(discord.errors.HTTPException, _explain_http_exception)
