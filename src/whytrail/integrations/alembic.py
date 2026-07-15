"""whytrail plugin for Alembic (ADR 0003).

Motivated by a real bug found in this project's own CI debugging, not
a hypothetical: a stale local `prefect.db` database (from an unrelated
earlier Alembic-migrated Prefect install) produced `alembic.util.exc.
CommandError: Can't locate revision identified by '79e7a60e43d8'` --
`str(exc)` alone doesn't say whether that revision ID came from the
database's own history, a `--sql` argument, or an ambiguous multiple-
heads situation, which is exactly the kind of detail
`RevisionError.argument`/`MultipleHeads.heads` already carry and a bare
traceback throws away.

No redaction needed here: revision identifiers and script arguments
aren't secrets, unlike a SQL statement's bound parameters (see
whytrail-sqlalchemy) or a task payload.
"""

from __future__ import annotations

from alembic.script.revision import MultipleHeads, ResolutionError, RevisionError
from alembic.util.exc import CommandError

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_resolution_error(exc: "ResolutionError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        ),
        ExplanationStep(
            description=f"the revision identifier that couldn't be resolved: {exc.argument!r}",
            confidence=Confidence.EXPLICIT.value,
            kind="value",
        ),
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def _explain_multiple_heads(exc: "MultipleHeads") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        ),
        ExplanationStep(
            description=f"{len(exc.heads)} head revisions are present, ambiguous for argument {exc.argument!r}: "
            f"{', '.join(exc.heads)}",
            confidence=Confidence.EXPLICIT.value,
            kind="value",
        ),
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def _explain_revision_error(exc: "RevisionError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def _explain_command_error(exc: "CommandError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def register() -> None:
    # Registered most-specific first -- resolve_explainer() walks the
    # MRO, so ResolutionError/MultipleHeads (which carry extra fields)
    # win over the generic RevisionError fallback for their own types.
    register_from_plugin(MultipleHeads, _explain_multiple_heads)
    register_from_plugin(ResolutionError, _explain_resolution_error)
    register_from_plugin(RevisionError, _explain_revision_error)
    register_from_plugin(CommandError, _explain_command_error)
