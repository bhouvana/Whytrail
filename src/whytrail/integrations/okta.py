"""whytrail plugin for okta-sdk-python, the Okta Management API client
(ADR 0003).

Found while building this: the SDK ships two separate, similarly-named
exception hierarchies from a merged/generated exceptions module --
`okta.exceptions.HTTPException`/`OktaAPIException` are empty
pass-through classes with no fields at all, while the real, structured
one actually raised by API calls (dispatched by status code via its
own `from_response()` classmethod) is
`okta.exceptions.exceptions.ApiException`, carrying `.status`,
`.reason`, `.body`, `.data`, and `.headers` -- confirmed by reading the
dispatch logic, not assumed from the shorter, more obviously-named
class.

`.body`/`.data` go through `locals`, not `description` (ADR 0002 §3
item 5): an Okta API error body can reference the specific user,
group, or application involved.
"""

from __future__ import annotations

import okta.exceptions.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "okta.exceptions.exceptions.ApiException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status}" + (f" ({exc.reason})" if exc.reason else "")
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    detail = exc.data or exc.body
    if detail:
        steps.append(
            ExplanationStep(
                description="response detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"detail": repr(detail)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(okta.exceptions.exceptions.ApiException, _explain_api_exception)
