"""whytrail plugin for Dagster (ADR 0003).

Not the same shape as most other plugins in this ecosystem, same
category as `whytrail[tenacity]`: `DagsterUserCodeExecutionError`
(covering `DagsterExecutionStepExecutionError` and friends) is a
*wrapper* Dagster's own execution engine puts around whatever
exception the user's op/asset code actually raised -- `.user_exception`
is that real underlying exception, `.original_exc_info` its original
`sys.exc_info()` tuple. A bare `str(exc)` shows Dagster's own
framework-level wrapper message, not the user code's actual failure.

This explainer unwraps to `.user_exception` and delegates to `why()`
recursively, the same "expand into the real cause" approach
`whytrail[tenacity]` already uses for `RetryError`. Step/op identity
(`.step_key`/`.op_name`/`.op_def_name`, when present -- only set on the
`DagsterExecutionStepExecutionError` subclass, not the base class) are
structural DAG coordinates, not user data, so they're safe directly in
`description` -- Dagster's own UI surfaces these same identifiers
unredacted. No redaction split is needed for the unwrapped exception
itself: the recursive `why()` call applies whatever redaction *that*
exception's own explainer already uses.
"""

from __future__ import annotations

import dagster._core.errors as dagster_errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_user_code_execution_error(exc: "dagster_errors.DagsterUserCodeExecutionError") -> Explanation:
    from whytrail import why

    step_key = getattr(exc, "step_key", None)
    op_name = getattr(exc, "op_name", None)
    location = f"step={step_key}, op={op_name}" if step_key or op_name else None
    subject = f"{type(exc).__name__}" + (f" ({location})" if location else "")
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]

    underlying = exc.user_exception
    if underlying is not None:
        inner = why(underlying)
        steps.append(
            ExplanationStep(
                description=f"user code raised: {type(underlying).__name__}",
                confidence=Confidence.INFERRED.value,
                kind="external",
            )
        )
        steps.extend(inner.steps)
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(dagster_errors.DagsterUserCodeExecutionError, _explain_user_code_execution_error)
