"""whytrail plugin for SQLAlchemy (ADR 0002 §7, Tier B).

`sqlalchemy.exc.StatementError` (the base of `IntegrityError`,
`OperationalError`, `ProgrammingError`, `DataError`, `DBAPIError`)
already carries exactly the structured detail a bare traceback
doesn't surface: the statement text, the bound parameters, and the
original driver exception. This plugin's whole job is exposing that
through `why()` instead of the generic tier-1 fallback, which only
ever showed `str(exc)` -- often just the driver's own message with no
statement or params attached.

Bound parameters go in `ExplanationStep.locals`, not `description`,
deliberately: a parameter set can contain exactly the kind of thing
ADR 0002 §3 item 5 flagged for locals -- a password hash, PII, a
token -- so it needs to go through the same `Explanation.redacted()`
path every other integration in this ecosystem uses before crossing a
process boundary (Sentry, OTel), not be exempt from it just because it
came from a query instead of a stack frame.

One honest caveat, found while auditing this same class of bug in
whytrail-pymongo (which discovered pymongo bakes redaction-intended data
into a place `.redacted()` couldn't reach): `description` here uses
`exc.orig` (the driver's own exception), not `exc.statement`/
`exc.params`, and that's been verified clean for sqlite3's driver
(`tests/plugin_contract/test_sqlalchemy_plugin.py`). Whether every
DBAPI driver's own error-message format is equally clean isn't
something this plugin can guarantee across all of them -- if you use a
driver whose error text embeds bound values, treat that as a driver
behavior to check, not something this plugin controls.
"""

from __future__ import annotations

import typing as t

import sqlalchemy.exc as sa_exc

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

__version__ = "0.1.0"


def _explain_statement_error(exc: "sa_exc.StatementError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc.orig!r}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    if exc.statement:
        steps.append(
            ExplanationStep(
                description=f"statement: {exc.statement.strip()}",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=_params_as_dict(exc.params),
            )
        )
    return Explanation(subject=f"{type(exc).__name__}: {exc.orig}", steps=steps, tracked=True)


def _params_as_dict(params: t.Any) -> dict[str, str] | None:
    if not params:
        return None
    if isinstance(params, dict):
        return {str(k): repr(v) for k, v in params.items()}
    if isinstance(params, (list, tuple)):
        return {str(i): repr(v) for i, v in enumerate(params)}
    return {"params": repr(params)}


def register() -> None:
    register_from_plugin(sa_exc.StatementError, _explain_statement_error)
