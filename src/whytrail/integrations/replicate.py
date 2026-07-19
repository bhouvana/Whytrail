"""whytrail plugin for the Replicate SDK (ADR 0003).

`ReplicateError` carries an RFC 7807 "problem details" structure --
`.type`, `.title`, `.status`, `.detail`, `.instance` -- detail a bare
`str(exc)` folds into one line.

`.detail` goes through `locals`, not `description` (ADR 0002 §3 item
5): it routinely echoes back the specific model version or input that
triggered the error.
"""

from __future__ import annotations

import replicate.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_replicate_error(exc: "replicate.exceptions.ReplicateError") -> Explanation:
    subject = f"{type(exc).__name__}: {exc.title}" if exc.title else type(exc).__name__
    if exc.status is not None:
        subject += f" (HTTP {exc.status})"
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    if exc.detail:
        steps.append(
            ExplanationStep(
                description="detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"detail": exc.detail},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(replicate.exceptions.ReplicateError, _explain_replicate_error)
