"""whytrail plugin for the Weaviate client SDK (ADR 0003).

Two distinct exception shapes, registered separately rather than at
the shared `WeaviateBaseError` base -- the base itself carries only a
plain `message` string (nothing structured to add over tier 1), so
registering it would be exactly the "polish, not capability" case ADR
0003 says isn't worth a plugin. `UnexpectedStatusCodeError` (any REST
call) and `WeaviateQueryError` (GraphQL/gRPC queries) each carry real
structured detail the base class doesn't: an HTTP/gRPC status code and
a raw response/query error, confirmed by reading the actual
constructors, not assumed from the class name.

The response/query detail goes through `locals`, not `description`
(ADR 0002 §3 item 5): it's the raw server response body, which can
echo back object properties or query content.
"""

from __future__ import annotations

import weaviate.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_status_code_error(exc: "weaviate.exceptions.UnexpectedStatusCodeError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description="response detail",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"error": repr(exc.error)} if exc.error is not None else None,
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def _explain_query_error(exc: "weaviate.exceptions.WeaviateQueryError") -> Explanation:
    # `protocol_type` (GraphQL vs gRPC) isn't retained as an attribute on
    # the exception itself -- only baked into the discarded formatted
    # message -- so the subject/description here stay generic rather than
    # guessing at it. exc.message/exc.error both carry the raw query
    # error text, which can echo back query content, so neither goes
    # anywhere but `locals` (ADR 0002 §3 item 5) -- confirmed by reading
    # the constructor, not assumed: an earlier draft put exc.message
    # directly in `subject`, which `Explanation.redacted()` does not
    # strip for an explainer-produced (non-graph-traversal) Explanation.
    subject = f"{type(exc).__name__}: query failed"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"error": exc.error},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(weaviate.exceptions.UnexpectedStatusCodeError, _explain_status_code_error)
    register_from_plugin(weaviate.exceptions.WeaviateQueryError, _explain_query_error)
