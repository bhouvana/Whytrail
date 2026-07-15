"""whytrail plugin for huggingface_hub (ADR 0003).

`HfHubHTTPError` subclasses `httpx.HTTPError` directly (not
`httpx.HTTPStatusError`), so it is *not* already covered by
whytrail-httpx's registrations -- verified via its MRO before writing
this, not assumed. It carries `.response` (status/URL) and
`server_message` (the Hub API's own error text), which `str(exc)`
doesn't cleanly separate.

`server_message` goes through `locals`: it's free-form text from the
Hub API and can contain repository names, usernames, or other account
detail, the same shape of risk as grpc's `.details()` or an LLM SDK's
response body (ADR 0002 §3 item 5).
"""

from __future__ import annotations

import typing as t

from huggingface_hub.errors import HfHubHTTPError

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

__version__ = "0.1.0"


def _explain_hf_hub_error(exc: "HfHubHTTPError") -> Explanation:
    response = exc.response
    request = response.request
    subject = f"{request.method} {request.url} -> {response.status_code}"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"server_message": exc.server_message} if exc.server_message else None,
        )
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(HfHubHTTPError, _explain_hf_hub_error)
