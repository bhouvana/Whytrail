"""whytrail plugin for the official kubernetes Python client (ADR 0003).

`kubernetes.client.exceptions.ApiException` carries the HTTP status
(`.status`), the HTTP reason phrase (`.reason` -- note: this is the
*HTTP* reason like `"Not Found"`, not the Kubernetes `Status` object's
own `reason` field like `"NotFound"`, which only exists inside
`.body`), and the raw JSON response body (`.body`, a `str`) --
collapsed by `str(exc)` into a multi-line but still unstructured
dump that's awkward to pull a specific field out of programmatically.

`.body` goes through `locals`, not `description` (ADR 0002 §3 item 5):
a Kubernetes API error message routinely echoes back the resource
name, namespace, and sometimes field values from the request that
shouldn't cross a process boundary unredacted by default. Only the
HTTP status and reason phrase -- structural metadata, never request
content -- are safe in `description`.
"""

from __future__ import annotations

import kubernetes.client.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_exception(exc: "kubernetes.client.exceptions.ApiException") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: {exc.reason}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    detail = f"status={exc.status}" if exc.status is not None else "response body"
    body_locals = {"body": str(exc.body)} if exc.body is not None else None
    if exc.status is not None or body_locals:
        steps.append(
            ExplanationStep(
                description=detail,
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=body_locals,
            )
        )
    subject = f"{type(exc).__name__}: {exc.status} {exc.reason}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(kubernetes.client.exceptions.ApiException, _explain_api_exception)
