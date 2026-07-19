"""whytrail plugin for the Temporal Python SDK (ADR 0003).

`ApplicationError` -- the exception a workflow/activity raises to
signal a business-logic failure -- carries retry semantics the
underlying failure protocol actually enforces (`.non_retryable`,
`.next_retry_delay`, `.category`) plus a free-form `.type` and
`.details` tuple, none of which survive a bare `str(exc)`.

`.details` goes through `locals`, not `description` (ADR 0002 §3 item
5): it's explicitly documented as "user-defined details," so it can
carry anything the workflow author chose to attach, including
sensitive payload data.
"""

from __future__ import annotations

import temporalio.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_application_error(exc: "temporalio.exceptions.ApplicationError") -> Explanation:
    subject = f"{type(exc).__name__}: {exc.type}" if exc.type else type(exc).__name__
    detail_parts = [f"non_retryable={exc.non_retryable}"]
    if exc.next_retry_delay is not None:
        detail_parts.append(f"next_retry_delay={exc.next_retry_delay}")
    if exc.category is not None:
        detail_parts.append(f"category={exc.category}")
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description=", ".join(detail_parts),
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"details": repr(exc.details)} if exc.details else None,
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(temporalio.exceptions.ApplicationError, _explain_application_error)
