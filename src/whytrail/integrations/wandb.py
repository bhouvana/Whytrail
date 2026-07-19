"""whytrail plugin for Weights & Biases (wandb) (ADR 0003).

`Error` carries an optional `.context` dict -- arbitrary structured
data W&B itself attaches for its own Sentry reporting -- that a bare
`str(exc)` never shows. `CommError` (errors communicating with W&B's
servers) additionally wraps `.exc`, the real underlying exception that
caused the communication failure -- the same "wrapper, not root cause"
shape `whytrail[tenacity]`/`whytrail[dagster]` already handle, so this
explainer delegates to `why()` recursively for that case instead of
just describing the wrapper.

`.context`/`.message` go through `locals`, not `description` (ADR 0002
§3 item 5): `.context` is explicitly a free-form bag of whatever the
caller attached, which can include run/project identifiers.
"""

from __future__ import annotations

import wandb.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_error(exc: "wandb.errors.Error") -> Explanation:
    from whytrail import why

    subject = type(exc).__name__
    context = getattr(exc, "context", None)
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.message, "context": repr(context)} if context else {"message": exc.message},
        ),
    ]

    underlying = getattr(exc, "exc", None)
    if underlying is not None:
        inner = why(underlying)
        steps.append(
            ExplanationStep(
                description=f"caused by: {type(underlying).__name__}",
                confidence=Confidence.INFERRED.value,
                kind="external",
            )
        )
        steps.extend(inner.steps)
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(wandb.errors.Error, _explain_error)
