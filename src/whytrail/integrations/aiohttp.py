"""whytrail plugin for aiohttp (ADR 0003).

`ClientResponseError` carries the request method/URL and response
status/message, which `str(exc)` doesn't cleanly separate. Unlike
requests/httpx, aiohttp's `raise_for_status()` doesn't keep the
response body accessible on the exception (the stream is already
being torn down by the time it raises), so there is no body-preview
step here the way there is for whytrail-requests/whytrail-httpx -- nothing
was omitted for redaction reasons, the data simply isn't available at
this point in aiohttp's own design.
"""

from __future__ import annotations

import typing as t

import aiohttp

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_response_error(exc: "aiohttp.ClientResponseError") -> Explanation:
    info = exc.request_info
    steps = [
        ExplanationStep(
            description=f"{info.method} {info.url} -> {exc.status} {exc.message}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    return Explanation(subject=f"{exc.status} {info.url}", steps=steps, tracked=True)


def _explain_connection_error(exc: "aiohttp.ClientConnectionError") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc}", confidence=Confidence.EXPLICIT.value, kind="external"
        )
    ]
    return Explanation(subject=f"{type(exc).__name__}: {exc}", steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(aiohttp.ClientResponseError, _explain_response_error)
    register_from_plugin(aiohttp.ClientConnectionError, _explain_connection_error)
