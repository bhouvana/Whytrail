"""whytrail plugin for pydantic (ADR 0003).

`ValidationError.errors()` already carries exactly the structured
detail a bare traceback throws away: which field, what kind of
mismatch, and the actual value that failed -- pydantic's own default
`str(exc)` renders this as a wall of text with every field's detail
concatenated, which is fine for a human eyeballing a single failure
but not something `why()`'s tier-1 fallback could improve on without
this plugin (tier 1 only sees `str(exc)` and the raise-site locals,
not pydantic's structured per-error list).

The bad *input value* for each field goes through `locals`, not
`description`, deliberately (ADR 0002 §3 item 5): a field that failed
validation is disproportionately likely to be exactly the kind of
thing that shouldn't cross a process boundary unredacted -- a
password, a token, a payment field.
"""

from __future__ import annotations

import typing as t

import pydantic

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

__version__ = "0.1.0"


def _explain_validation_error(exc: "pydantic.ValidationError") -> Explanation:
    errors = exc.errors(include_url=False)
    steps = [
        ExplanationStep(
            description=f"{exc.error_count()} validation error(s) for {exc.title}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    for err in errors:
        loc = ".".join(str(part) for part in err.get("loc", ()))
        description = f"field {loc!r}: {err.get('msg', '')} ({err.get('type', 'unknown')})"
        locals_: dict[str, str] | None = None
        if "input" in err:
            locals_ = {"input": repr(err["input"])}
        steps.append(
            ExplanationStep(
                description=description,
                confidence=Confidence.EXPLICIT.value,
                kind="value",
                locals=locals_,
            )
        )
    return Explanation(subject=f"{exc.error_count()} validation error(s) for {exc.title}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pydantic.ValidationError, _explain_validation_error)
