"""whytrail plugin for azure-core (shared base of every Azure SDK client:
azure-storage-blob, azure-identity, azure-cosmos, etc.) (ADR 0003).

`azure.core.exceptions.HttpResponseError` carries the HTTP status
(`.status_code`), the HTTP reason phrase (`.reason`), and -- when the
service responded in Azure's standard OData error format, which most
of them do -- a parsed `.error` object with its own `.code` (a stable
taxonomy string like `"BlobNotFound"`) and `.message`. `str(exc)`
collapses all of it into `.message` alone, dropping the status code
and the machine-readable `.error.code` a caller would branch on.

`.error.code` is a stable, closed taxonomy string (Azure's own error
code, not request content) and stays in `description`, the same
posture as whytrail-stripe's `.code`. The full `.error.message` (which
routinely echoes a request ID, a resource name, or path) goes through
`locals`, not `description` (ADR 0002 §3 item 5).
"""

from __future__ import annotations

import azure.core.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_http_response_error(exc: "azure.core.exceptions.HttpResponseError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc.reason}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    error = getattr(exc, "error", None)
    code = getattr(error, "code", None) if error is not None else None
    detail_parts = []
    if exc.status_code is not None:
        detail_parts.append(f"status_code={exc.status_code}")
    if code:
        detail_parts.append(f"code={code}")
    message_locals = {"message": str(exc.message)} if exc.message else None
    if detail_parts or message_locals:
        steps.append(
            ExplanationStep(
                description=", ".join(detail_parts) if detail_parts else "response detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=message_locals,
            )
        )
    subject = f"{type(exc).__name__}: {exc.status_code} {code or exc.reason}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(azure.core.exceptions.HttpResponseError, _explain_http_response_error)
