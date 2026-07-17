"""whytrail plugin for the sendgrid Python SDK (ADR 0003).

SendGrid's SDK is built on `python_http_client`, and its API errors
(`BadRequestsError`, `UnauthorizedError`, ... all subclasses of
`python_http_client.exceptions.HTTPError`) carry `.status_code`/
`.reason`/`.body`/`.headers` -- SendGrid's own structured API response,
squashed by the base `Exception.__str__` into a single unstructured
4-tuple repr with no separation between status metadata and the raw
response body.

`.body` (SendGrid's raw JSON error response) goes through `locals`,
not `description` (ADR 0002 §3 item 5): SendGrid's own error messages
routinely echo back the offending field or email address from the
request. Only `.status_code`/`.reason` -- structural HTTP metadata,
never request content -- are safe in `description`.
"""

from __future__ import annotations

import python_http_client.exceptions as _http_exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_http_error(exc: "_http_exceptions.HTTPError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: HTTP {exc.status_code} {exc.reason}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    body = getattr(exc, "body", None)
    if body:
        body_str = body.decode("utf-8", errors="replace") if isinstance(body, bytes) else str(body)
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"body": body_str},
            )
        )
    subject = f"{type(exc).__name__}: {exc.status_code} {exc.reason}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(_http_exceptions.HTTPError, _explain_http_error)
