"""whytrail plugin for PyMySQL (ADR 0003).

`pymysql.err.Error` subclasses (`OperationalError`, `IntegrityError`,
`ProgrammingError`, ...) carry `args = (errno, message)` -- a real
MySQL error number (a stable taxonomy, e.g. `1054` = unknown column)
and the driver's own message, which `str(exc)` folds into one tuple
repr with no separation between the two.

`args[1]` (the driver message) goes through `locals`, not
`description` (ADR 0002 §3 item 5): MySQL error messages routinely
embed the offending column/table name directly. `args[0]` (the error
number) is a small closed taxonomy, safe in `description`.
"""

from __future__ import annotations

import pymysql.err

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_pymysql_error(exc: "pymysql.err.Error") -> Explanation:
    errno = exc.args[0] if exc.args else None
    message = exc.args[1] if len(exc.args) > 1 else None
    subject = f"{type(exc).__name__} (errno {errno})" if errno is not None else type(exc).__name__
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
    register_from_plugin(pymysql.err.Error, _explain_pymysql_error)
