"""whytrail plugin for pyodbc (ADR 0003).

`pyodbc.Error` (and its subclasses like `pyodbc.IntegrityError`,
`pyodbc.ProgrammingError`) carries the driver's SQLSTATE code as
`exc.args[0]` and the driver's own message as `exc.args[1]` -- a real,
5-character, ISO/ODBC-standard taxonomy string (e.g. `"42S02"` = table
not found, `"23000"` = integrity constraint violation) that a bare
`str(exc)` only shows concatenated with the message inside a tuple
repr, not as something a caller can branch on. `vars(exc)` is empty --
pyodbc doesn't expose named attributes, only `.args` -- confirmed by
inspection, not assumed from psycopg2's C-level-attribute precedent
(ADR 0003 already found psycopg2's `.pgcode`/`.pgerror` blocked outside
a real connection; pyodbc's `.args` tuple has no such constraint).

`args[1]` (the driver message) goes through `locals`, not
`description` (ADR 0002 §3 item 5): ODBC driver messages routinely
embed the offending table/column/value directly in the text. The
SQLSTATE code alone -- a small closed taxonomy, not request content --
is safe in `description`.
"""

from __future__ import annotations

import pyodbc as _pyodbc

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_pyodbc_error(exc: "_pyodbc.Error") -> Explanation:
    sqlstate = exc.args[0] if exc.args else None
    message = exc.args[1] if len(exc.args) > 1 else None
    subject = f"{type(exc).__name__} (sqlstate {sqlstate})" if sqlstate else type(exc).__name__
    steps = [
        ExplanationStep(
            description=subject,
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
    register_from_plugin(_pyodbc.Error, _explain_pyodbc_error)
