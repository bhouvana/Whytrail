"""whytrail plugin for the Square SDK (ADR 0003).

`ApiError` carries the HTTP status code and a parsed `errors` list
(each with a `category`/`code` taxonomy plus a `detail`/`field`) --
detail that's genuinely structured, unlike what it looks like at
first: `str(exc)`/`exc.args[0]` already bakes the *entire* raw response
body into the exception's own message (`ApiError._build_message`), so
neither the built-in message nor a naive `repr(exc)` is safe to reuses
here -- this explainer reads `.status_code`/`.errors` directly instead
of parsing that pre-built string.

`category`/`code` (a closed, documented taxonomy -- see
docs/build-basics/handling-errors) are safe in `description`; `detail`
goes through `locals`, not `description` (ADR 0002 §3 item 5): it's a
free-text field that can reference the specific payment, card, or
customer involved.
"""

from __future__ import annotations

import square.core.api_error

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "square.core.api_error.ApiError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    for error in exc.errors or []:
        category = getattr(error, "category", None)
        code = getattr(error, "code", None)
        detail = getattr(error, "detail", None)
        steps.append(
            ExplanationStep(
                description=f"{category}: {code}" if category or code else "error detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"detail": detail} if detail else None,
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(square.core.api_error.ApiError, _explain_api_error)
