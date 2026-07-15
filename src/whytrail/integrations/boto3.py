"""whytrail plugin for boto3/botocore (ADR 0003).

`ClientError.response` already carries exactly the structured detail
AWS itself returned -- error code, message, HTTP status, request ID --
which botocore's own `str(exc)` squashes into a single line. The
exception botocore actually raises is a *dynamically generated*
subclass of `ClientError` (`NoSuchKey`, `AccessDenied`,
`ThrottlingException`, ...), created per service at runtime by
`botocore.errorfactory` -- registering the explainer against the base
`ClientError` class is what makes it resolve for all of them via
whytrail's MRO walk, without needing to know every service's error
vocabulary in advance.

No locals-redaction concern here worth a special case: `.response`
carries AWS's own error description, not the request parameters that
triggered it (boto3 doesn't attach those to the exception), so there's
nothing here that plausibly holds a secret the way a SQL param or a
Pydantic field value can.
"""

from __future__ import annotations

import typing as t

from botocore.exceptions import ClientError

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_client_error(exc: "ClientError") -> Explanation:
    error = exc.response.get("Error", {})
    metadata = exc.response.get("ResponseMetadata", {})
    code = error.get("Code", "Unknown")
    message = error.get("Message", str(exc))
    status = metadata.get("HTTPStatusCode")
    request_id = metadata.get("RequestId")

    steps = [
        ExplanationStep(
            description=f"{exc.operation_name} failed: {code} -- {message}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    detail_parts = []
    if status is not None:
        detail_parts.append(f"HTTP {status}")
    if request_id:
        detail_parts.append(f"request id {request_id}")
    if detail_parts:
        steps.append(
            ExplanationStep(description=", ".join(detail_parts), confidence=Confidence.EXPLICIT.value, kind="external")
        )

    return Explanation(subject=f"{exc.operation_name}: {code}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(ClientError, _explain_client_error)
