"""whytrail plugin for pymssql (ADR 0003).

`pymssql.Error` subclasses carry `args[0]` as a `(code, message)` tuple
-- a real SQL Server/DB-Lib error code and message, which `str(exc)`
folds into one tuple repr with no separation.

The message goes through `locals`, not `description` (ADR 0002 §3 item
5): DB-Lib error messages routinely embed the offending object name
directly. The numeric code is a small closed taxonomy, safe in
`description`.
"""

from __future__ import annotations

import pymssql

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_pymssql_error(exc: "pymssql.Error") -> Explanation:
    detail = exc.args[0] if exc.args else None
    code, message = (None, None)
    if isinstance(detail, tuple) and len(detail) == 2:
        code, message = detail
    subject = f"{type(exc).__name__} (code {code})" if code is not None else type(exc).__name__
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    if message:
        message_str = message.decode("utf-8", errors="replace") if isinstance(message, bytes) else str(message)
        steps.append(
            ExplanationStep(
                description="driver message",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"message": message_str},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pymssql.Error, _explain_pymssql_error)
