"""whytrail plugin for the stripe SDK (ADR 0003).

`stripe.StripeError` (covering `CardError`, `InvalidRequestError`,
`AuthenticationError`, `RateLimitError`, `APIConnectionError`, ...)
already carries the HTTP status, the API's own error code, which
request parameter triggered it, and the full structured error body --
detail `str(exc)` collapses into one line, and exactly the kind of
"why did this payment fail" question a bare traceback can't answer.

The error body and `.param` go through `locals`, not `description`,
deliberately (ADR 0002 §3 item 5): a payment error's body can echo back
request detail (a customer's name, a partial card description) that
shouldn't cross a process boundary unredacted by default -- the same
posture as whytrail-openai's response body.
"""

from __future__ import annotations

import stripe

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_stripe_error(exc: "stripe.StripeError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc.user_message or str(exc)}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    detail_parts = []
    if exc.code:
        detail_parts.append(f"code={exc.code}")
    # getattr(), not exc.param directly: only some StripeError subclasses
    # (CardError, InvalidRequestError) actually declare .param -- the
    # base class this explainer is registered against doesn't. Reusing
    # the fetched value (rather than re-accessing exc.param in the
    # f-string below) is also what makes this type-check cleanly under
    # mypy --strict instead of asserting a type mypy can't verify.
    param = getattr(exc, "param", None)
    if param:
        detail_parts.append(f"param={param}")
    if exc.http_status:
        detail_parts.append(f"http_status={exc.http_status}")
    body_locals = {"json_body": repr(exc.json_body)} if exc.json_body is not None else None
    if detail_parts or body_locals:
        steps.append(
            ExplanationStep(
                description=", ".join(detail_parts) if detail_parts else "response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=body_locals,
            )
        )
    subject = f"{type(exc).__name__}: {exc.user_message or str(exc)}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(stripe.StripeError, _explain_stripe_error)
