"""whytrail plugin for asyncpg (ADR 0003).

`PostgresError` already carries the same structured detail PostgreSQL
itself reports -- SQLSTATE code, constraint/table/column name, detail,
hint -- which `str(exc)` reduces to the message alone. Registered
against the base `PostgresError`, so every specific error
(`UniqueViolationError`, `ForeignKeyViolationError`, ...) resolves via
whytrail's MRO walk.

Constraint/table/column *names* are schema metadata, not user data, and
go in `description`. `detail` can echo back an offending row's actual
values (the same shape of risk as SQLAlchemy's bound params), so it
goes through `locals` for the same redaction reasons as ADR 0002 §3
item 5.
"""

from __future__ import annotations

import typing as t

import asyncpg

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

__version__ = "0.1.0"


def _explain_postgres_error(exc: "asyncpg.PostgresError") -> Explanation:
    # Deliberately not f"...{exc}": asyncpg's own PostgresError.__str__
    # auto-appends "\nDETAIL: ..." to the message, which would leak the
    # same sensitive detail this function puts in `locals` right back
    # into `description` where Explanation.redacted() can't reach it.
    # exc.args[0] is the bare message asyncpg was constructed with.
    message = exc.args[0] if exc.args else type(exc).__name__
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__} (sqlstate {exc.sqlstate}): {message}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    where_parts = []
    for attr in ("table_name", "column_name", "constraint_name"):
        value = getattr(exc, attr, None)
        if value:
            where_parts.append(f"{attr}={value}")
    detail = getattr(exc, "detail", None)
    if where_parts or detail:
        steps.append(
            ExplanationStep(
                description=", ".join(where_parts) if where_parts else "detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"detail": detail} if detail else None,
            )
        )
    return Explanation(subject=f"{type(exc).__name__}: {message}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(asyncpg.PostgresError, _explain_postgres_error)
