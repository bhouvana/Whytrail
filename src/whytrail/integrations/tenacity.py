"""whytrail plugin for tenacity (ADR 0003).

Not the same shape as every other plugin in this ecosystem: `str()` on
a bare `tenacity.RetryError` doesn't just squash structured data into
one line, it hides the actual failure entirely --
`RetryError[<Future at 0x... state=finished raised ValueError>]` --
with no indication of what the wrapped exception actually was or said.
`.last_attempt` is a `concurrent.futures.Future`-shaped object whose
`.exception()` is the real underlying exception every retry attempt
raised, and `.attempt_number` is how many attempts were made before
giving up.

This explainer unwraps to that underlying exception and delegates to
`why()` recursively, the same "expand into the real cause" approach
`explain_exception()` already uses for `ExceptionGroup`'s
sub-exceptions -- a `RetryError` isn't really its own root cause, it's
a wrapper around one. No redaction split is needed here (unlike every
HTTP/driver-error plugin in this ecosystem): the recursive `why()` call
on the unwrapped exception applies whatever redaction *that* exception's
own explainer already uses.
"""

from __future__ import annotations

import tenacity

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_retry_error(exc: "tenacity.RetryError") -> Explanation:
    # Local import: whytrail.why() is only ever reachable once whytrail
    # itself has finished importing (this module is only ever loaded
    # lazily, on demand, from inside a running why() call) -- a
    # module-level `import whytrail` would work too, but this makes the
    # "avoid a real circular import at package-init time" reasoning
    # explicit rather than relying on import order happening to work out.
    from whytrail import why

    attempt = exc.last_attempt
    attempt_number = getattr(attempt, "attempt_number", None)
    subject = f"RetryError after {attempt_number} attempt(s)" if attempt_number else "RetryError"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    underlying = attempt.exception() if attempt is not None else None
    if underlying is not None:
        inner = why(underlying)
        steps.append(
            ExplanationStep(
                description=f"last attempt raised: {type(underlying).__name__}",
                confidence=Confidence.INFERRED.value,
                kind="external",
            )
        )
        steps.extend(inner.steps)
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(tenacity.RetryError, _explain_retry_error)
