"""whytrail plugin for psycopg (v3) (ADR 0003).

Not the same verdict as `psycopg2`, already found blocked elsewhere in
this ecosystem: psycopg2's `.pgcode`/`.pgerror` are C-level, read-only
`member_descriptor` attributes populated only by a real PostgreSQL
connection. `psycopg` (the v3 rewrite)'s `.sqlstate` is a plain,
settable Python attribute -- confirmed directly by constructing one and
setting it, not assumed from the successor relationship. `str(exc)`
shows the message alone, dropping the SQLSTATE code entirely.

`psycopg`'s richer `.diag` object (`.table_name`, `.constraint_name`,
`.message_detail`, ...) *is* still read-only outside a real connection,
same constraint as psycopg2 -- not used here for that reason; this
plugin is deliberately more modest than `whytrail-asyncpg`'s
(async-only) coverage of the same database, using only what's provably
available without a live connection: `.sqlstate` and the exception's
own message.

The message goes through `locals`, not `description` (ADR 0002 §3 item
5): PostgreSQL error messages routinely embed the offending
table/column/value directly. `.sqlstate` is a small closed taxonomy,
safe in `description`.
"""

from __future__ import annotations

import psycopg

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_psycopg_error(exc: "psycopg.Error") -> Explanation:
    sqlstate = getattr(exc, "sqlstate", None)
    subject = f"{type(exc).__name__} (sqlstate {sqlstate})" if sqlstate else type(exc).__name__
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    message = str(exc)
    if message:
        steps.append(
            ExplanationStep(
                description="driver message",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"message": message},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(psycopg.Error, _explain_psycopg_error)
