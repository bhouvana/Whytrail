"""whytrail plugin for the Pinecone SDK (ADR 0003).

`PineconeApiException` (covering `NotFoundException`,
`UnauthorizedException`, `ForbiddenException`, ...) carries the HTTP
status code, the API's own error code/request id, and a structured
response body -- detail `str(exc)` truncates into one line.

Found while building this (not assumed from the README): the PyPI
distribution `pinecone-client` is deprecated and raises on import,
telling you to install `pinecone` instead -- this plugin targets the
current `pinecone` package, not the renamed one.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): it can echo back the index/namespace name or query detail
that triggered the error.
"""

from __future__ import annotations

import pinecone.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "pinecone.exceptions.PineconeApiException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    detail_parts = []
    if exc.error_code:
        detail_parts.append(f"error_code={exc.error_code}")
    if exc.request_id:
        detail_parts.append(f"request_id={exc.request_id}")
    body_locals = {"body": repr(exc.body)} if exc.body is not None else None
    if detail_parts or body_locals:
        steps.append(
            ExplanationStep(
                description=", ".join(detail_parts) if detail_parts else "response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=body_locals,
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pinecone.exceptions.PineconeApiException, _explain_api_exception)
