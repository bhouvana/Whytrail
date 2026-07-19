"""whytrail plugin for the Supabase Python SDK (ADR 0003).

Found while building this: `supabase-py`'s database errors are raised
by its underlying PostgREST client, not by `supabase` itself --
`postgrest.exceptions.APIError` (PostgreSQL's own error code/hint/
details, surfaced through PostgREST) is the real, structured exception
type, confirmed by tracing what a `supabase.Client().table(...)` call
actually raises rather than assumed from the `supabase` package's own
top-level namespace (which exposes no exception types of its own).

`.message`/`.hint`/`.details` go through `locals`, not `description`
(ADR 0002 §3 item 5): a Postgres constraint-violation hint or detail
routinely echoes back the actual row value that violated it.
"""

from __future__ import annotations

import postgrest.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "postgrest.exceptions.APIError") -> Explanation:
    subject = f"{type(exc).__name__}: {exc.code}" if exc.code else type(exc).__name__
    locals_ = {k: v for k, v in {"message": exc.message, "hint": exc.hint, "details": exc.details}.items() if v}
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals=locals_ or None,
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(postgrest.exceptions.APIError, _explain_api_error)
