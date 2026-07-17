"""whytrail plugin for oracledb (ADR 0003).

`oracledb.Error`'s `args[0]` is a real `oracledb.errors._Error` object
carrying `.full_code` (a stable `"ORA-12545"`-style taxonomy string),
`.offset` (position in the SQL where the error occurred), and
`.isrecoverable`/`.iswarning` -- structured detail a bare `str(exc)`
squashes into one message line. Confirmed directly against a real
connection error (not a live database -- oracledb's thin-mode driver
populates a real `_Error` object even for a connection-level failure
against an unreachable host), unlike `psycopg2`, whose equivalent
`.pgcode`/`.pgerror` ADR 0003 already found are C-level, read-only
attributes populated only by a real PostgreSQL connection -- a
different constraint, checked separately rather than assumed to be the
same problem.

`.message` goes through `locals`, not `description` (ADR 0002 §3 item
5): Oracle's own error text routinely echoes back the offending
table/column/bind value. `.full_code`/`.offset` -- structural metadata,
never request content -- are safe in `description`.
"""

from __future__ import annotations

import oracledb

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_oracledb_error(exc: "oracledb.Error") -> Explanation:
    detail = exc.args[0] if exc.args else None
    full_code = getattr(detail, "full_code", None)
    offset = getattr(detail, "offset", None)
    message = getattr(detail, "message", None)

    subject = f"{type(exc).__name__} ({full_code})" if full_code else type(exc).__name__
    desc_parts = [subject]
    if offset:
        desc_parts.append(f"offset={offset}")
    steps = [
        ExplanationStep(
            description=", ".join(desc_parts),
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    if message:
        steps.append(
            ExplanationStep(
                description="driver message",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"message": str(message)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(oracledb.Error, _explain_oracledb_error)
