"""whytrail plugin for the Meilisearch SDK (ADR 0003).

`MeilisearchApiError` carries the HTTP status code plus Meilisearch's
own structured error fields -- `.code` (a stable, documented error
code), `.type`, and `.link` (a URL to the specific error's
documentation page) -- detail a bare `str(exc)` folds into one line.

`.message` goes through `locals`, not `description` (ADR 0002 §3 item
5): it can echo back the index name or document ID involved.
"""

from __future__ import annotations

import meilisearch.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "meilisearch.errors.MeilisearchApiError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}" + (f" ({exc.code})" if exc.code else "")
    detail_parts = []
    if exc.type:
        detail_parts.append(f"type={exc.type}")
    if exc.link:
        detail_parts.append(f"link={exc.link}")
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description=", ".join(detail_parts) if detail_parts else "message",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.message} if exc.message else None,
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(meilisearch.errors.MeilisearchApiError, _explain_api_error)
