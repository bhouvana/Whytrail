"""whytrail plugin for the Mistral AI SDK (ADR 0003).

`MistralError` (the SDK's shared HTTP error base, covering `SDKError`
and friends) carries the HTTP status code, response headers, and raw
response body -- the same structured-error shape as
`whytrail[openai]`/`whytrail[anthropic]`/`whytrail[cohere]`.

Found while building this: the installed SDK's real client class lives
at `mistralai.client.Mistral`, not `mistralai.Mistral` -- the top-level
`mistralai` package is a PEP 420 namespace package (shared with
`mistralai-azure`/`mistralai-gcp` sibling distributions) with no code
of its own, confirmed directly rather than assumed from the README.
Its error module is at `mistralai.client.errors` accordingly.

The response body goes through `locals`, not `description` (ADR 0002
§3 item 5): it can echo back the prompt/message content that triggered
a validation error.
"""

from __future__ import annotations

from mistralai.client import errors as mistralai_errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_mistral_error(exc: "mistralai_errors.MistralError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
    ]
    if exc.body:
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"body": exc.body},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(mistralai_errors.MistralError, _explain_mistral_error)
