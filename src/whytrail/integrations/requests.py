"""whytrail plugin for the `requests` library (ADR §06, §13).

Demonstrates the entry-point plugin architecture end to end: this
module never imports whytrail's internals beyond the public registration
API, and whytrail's core never imports requests. Discovered lazily via
the `whytrail.explainers` entry point on first why() call.

Response bodies go through `ExplanationStep.locals`, not
`description` (retrofitted after ADR 0002 §3 item 5's core fix landed
-- this plugin predates it): a REST API's error response can echo back
request data the same way an LLM API's response body can (see
whytrail-openai/whytrail-anthropic), so it gets the same redaction
treatment, not an exemption because it came from `requests` instead.
"""

from __future__ import annotations

import typing as t

import requests

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _safe_str(value: t.Any) -> str:
    """requests' own `PreparedRequest.method`/`.url` are typed to allow
    `bytes` (its `prepare_method()`/`prepare_url()` accept bytes input
    from a caller before normalizing to `str`) -- confirmed by mypy
    --strict flagging the bare f-string interpolation below
    (str-bytes-safe: an f-string on a bytes value produces `"b'GET'"`,
    not `"GET"`, which looks like a formatting bug even though it's
    technically correct). By the time an exception reaches this
    explainer that's normalized to `str` in every real case, but this
    handles the type honestly instead of asserting it away."""
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else str(value)


def _explain_response(response: "requests.Response") -> Explanation:
    request = response.request
    method = _safe_str(request.method) if request is not None else "?"
    steps = [
        ExplanationStep(
            description=f"{method} {response.url} -> {response.status_code} {response.reason}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    if not response.ok:
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"body": response.text[:200]},
            )
        )
    return Explanation(subject=f"{response.status_code} {response.url}", steps=steps, tracked=True)


def _explain_request_exception(exc: "requests.exceptions.RequestException") -> Explanation:
    request = exc.request
    response = exc.response
    steps: list[ExplanationStep] = []
    if request is not None:
        steps.append(
            ExplanationStep(
                description=f"{_safe_str(request.method)} {_safe_str(request.url)} was sent",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
            )
        )
    if response is not None:
        steps.append(
            ExplanationStep(
                description=f"server responded {response.status_code} {response.reason}",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
            )
        )
    steps.append(
        ExplanationStep(
            description=f"raised as {type(exc).__name__}: {exc}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    )
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def register() -> None:
    """The function the `whytrail.explainers` entry point in
    pyproject.toml points to. Called once, lazily, the first time
    whytrail needs to resolve an explainer it doesn't already have."""
    register_from_plugin(requests.Response, _explain_response)
    register_from_plugin(requests.exceptions.RequestException, _explain_request_exception)
