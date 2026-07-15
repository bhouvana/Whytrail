"""whytrail plugin for Google Cloud SDKs (ADR 0003).

`google.api_core.exceptions.GoogleAPICallError` is the shared base
every google-cloud-* client library raises from (storage, bigquery,
pubsub, firestore, ...) -- registering against it, rather than a
storage-specific type, covers the whole family from one plugin.
Carries `.code` (HTTP-style status), `.reason`/`.domain` (structured
error classification), and `.details` (a list of arbitrary extra
detail strings).

`.message` stays in `description`: unlike pymongo/jsonschema/asyncpg
(where the driver's own text was found to embed arbitrary *document
content*), a GoogleAPICallError's message identifies *which resource*
the call was against (e.g. "bucket some-bucket not found") -- the same
category of content a URL already is in every HTTP-based plugin in
this ecosystem, not free-form data. `.details` is more open-ended
(exactly how open-ended varies by service) and goes through `locals`
for the same reason as grpc's `.details()`.
"""

from __future__ import annotations

import typing as t

from google.api_core.exceptions import GoogleAPICallError

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_call_error(exc: "GoogleAPICallError") -> Explanation:
    parts = [f"{type(exc).__name__} (code={exc.code})"]
    if exc.reason:
        parts.append(f"reason={exc.reason}")
    subject = f"{type(exc).__name__}: {exc.message}"

    steps = [
        ExplanationStep(
            description=f"{', '.join(parts)}: {exc.message}",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"details": repr(exc.details)} if exc.details else None,
        )
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(GoogleAPICallError, _explain_api_call_error)
