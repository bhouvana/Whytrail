"""whytrail plugin for snowflake-connector-python (ADR 0003).

`snowflake.connector.errors.Error` subclasses carry `.errno`/
`.sqlstate` (a numeric Snowflake error code and standard SQLSTATE),
`.sfqid` (the Snowflake query ID -- safe, useful for cross-referencing
Snowflake's own query history UI), and `.raw_msg`/`.query` -- all
folded by `str(exc)` into one combined `"NNNNNN (SQLSTATE): message"`
line that's awkward to parse a specific field back out of
programmatically.

`.raw_msg`/`.query` go through `locals`, not `description` (ADR 0002
§3 item 5): the raw message routinely echoes the offending object
name, and `.query` is the literal SQL text that failed -- the same
redaction posture as SQLAlchemy's bound params. `.errno`/`.sqlstate`/
`.sfqid` -- structural metadata, never request content -- are safe in
`description`.
"""

from __future__ import annotations

import snowflake.connector.errors as _sf_errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_snowflake_error(exc: "_sf_errors.Error") -> Explanation:
    errno = getattr(exc, "errno", None)
    sqlstate = getattr(exc, "sqlstate", None)
    sfqid = getattr(exc, "sfqid", None)
    subject = f"{type(exc).__name__} (errno {errno}, sqlstate {sqlstate})" if errno else type(exc).__name__
    desc_parts = [subject]
    if sfqid:
        desc_parts.append(f"sfqid={sfqid}")
    steps = [
        ExplanationStep(
            description=", ".join(desc_parts),
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    raw_msg = getattr(exc, "raw_msg", None)
    query = getattr(exc, "query", None)
    locals_dict = {}
    if raw_msg:
        locals_dict["message"] = str(raw_msg)
    if query:
        locals_dict["query"] = str(query)
    if locals_dict:
        steps.append(
            ExplanationStep(
                description="query detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=locals_dict,
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(_sf_errors.Error, _explain_snowflake_error)
