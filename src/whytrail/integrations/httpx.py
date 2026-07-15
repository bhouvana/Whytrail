"""whytrail plugin for httpx (ADR 0003).

Same shape as whytrail-requests, for the same reason: `HTTPStatusError`
and `RequestError` already carry the method, URL, and response detail
that a bare `str(exc)` throws away. Response body goes through
`ExplanationStep.locals`, for the same redaction reasons as
whytrail-requests and whytrail-openai/anthropic (ADR 0002 §3 item 5).
"""

from __future__ import annotations

import typing as t

import httpx

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_status_error(exc: "httpx.HTTPStatusError") -> Explanation:
    request, response = exc.request, exc.response
    steps = [
        ExplanationStep(
            description=f"{request.method} {request.url} -> {response.status_code} {response.reason_phrase}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    if not response.is_success:
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"body": response.text[:200]},
            )
        )
    return Explanation(subject=f"{response.status_code} {request.url}", steps=steps, tracked=True)


def _explain_request_error(exc: "httpx.RequestError") -> Explanation:
    request = exc.request
    description = f"{request.method} {request.url} failed: {type(exc).__name__}: {exc}"
    steps = [ExplanationStep(description=description, confidence=Confidence.EXPLICIT.value, kind="external")]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(httpx.HTTPStatusError, _explain_status_error)
    register_from_plugin(httpx.RequestError, _explain_request_error)
