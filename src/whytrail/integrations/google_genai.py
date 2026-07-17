"""whytrail plugin for the google-genai SDK (Gemini API) (ADR 0003).

Note: the older `google-generativeai` package is officially deprecated
(a `FutureWarning` fires on import, pointing at this successor) and its
errors route through `google.api_core.exceptions.GoogleAPICallError`
-- already covered by `whytrail-google-cloud`, confirmed directly, not
assumed. `google-genai` is architecturally separate: its own
`google.genai.errors.APIError` hierarchy, not built on `google-cloud`'s
`api_core` at all.

`APIError` carries `.code`/`.status`/`.message`/`.details` -- the raw
parsed API error response, squashed by `str(exc)` into whatever
`__str__` happens to produce. `.message`/`.details` go through
`locals`, not `description` (ADR 0002 §3 item 5): a Gemini API error
message routinely echoes back the offending request detail (a bad
model name, a content-safety rejection quoting the input). `.code`/
`.status` -- a numeric HTTP-style code and a stable enum string like
`"INVALID_ARGUMENT"` -- are safe in `description`.
"""

from __future__ import annotations

import google.genai.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "google.genai.errors.APIError") -> Explanation:
    code = exc.code
    status = exc.status
    message = exc.message
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: code={code} status={status}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    if message:
        steps.append(
            ExplanationStep(
                description="response message",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"message": str(message)},
            )
        )
    subject = f"{type(exc).__name__}: {code} {status}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(google.genai.errors.APIError, _explain_api_error)
