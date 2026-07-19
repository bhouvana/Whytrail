"""whytrail plugin for ChromaDB (ADR 0003).

`ChromaError` carries a real per-subclass taxonomy -- `.code()` (an
HTTP-equivalent status each subclass overrides, e.g.
`NotFoundError`/`QuotaError`), `.name()` (a stable error name), and an
optional `.trace_id` -- accessed via methods rather than plain
attributes (confirmed by reading the base class), but still real
structured data a bare `str(exc)` doesn't expose as separately
queryable fields.

`.message()` goes through `locals`, not `description` (ADR 0002 §3
item 5): it can echo back the collection name or document ID involved.
"""

from __future__ import annotations

import chromadb.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_chroma_error(exc: "chromadb.errors.ChromaError") -> Explanation:
    subject = f"{type(exc).__name__}: {exc.name()} (HTTP {exc.code()})"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.message(), "trace_id": exc.trace_id or ""},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(chromadb.errors.ChromaError, _explain_chroma_error)
