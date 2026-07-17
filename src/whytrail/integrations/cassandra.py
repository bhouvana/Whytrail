"""whytrail plugin for the DataStax cassandra-driver (ADR 0003).

Registers against `RequestExecutionException`, not the driver's own
top-level `DriverException` -- checked directly, not assumed: sibling
type `InvalidRequest` (under the separate `RequestValidationException`
branch) carries nothing but a plain message, the same shape ADR 0003
already rejects elsewhere in this ecosystem. `RequestExecutionException`
specifically covers `Unavailable`/`WriteTimeout`/`ReadTimeout` --
Cassandra's consistency-level coordination failures, and genuinely
structured: `.consistency`/`.required_replicas`/`.alive_replicas` (or
`.required_responses`/`.received_responses`/`.write_type` for the
timeout variants), all of it dropped by `str(exc)`'s plain message.

No redaction concern here: every field on these specific exception
types is coordination metadata (consistency levels, replica counts),
never query content or row data, so nothing needs to route through
`locals`.
"""

from __future__ import annotations

from cassandra import RequestExecutionException

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin

_FIELDS = (
    "consistency",
    "required_replicas",
    "alive_replicas",
    "required_responses",
    "received_responses",
    "write_type",
)


def _explain_coordination_failure(exc: "RequestExecutionException") -> Explanation:
    detail_parts = []
    for field in _FIELDS:
        value = getattr(exc, field, None)
        if value is not None:
            detail_parts.append(f"{field}={value}")

    subject = type(exc).__name__
    steps = [
        ExplanationStep(
            description=f"{subject}: {exc}",
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    if detail_parts:
        steps.append(
            ExplanationStep(
                description=", ".join(detail_parts),
                confidence=Confidence.EXPLICIT.value,
                kind="external",
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(RequestExecutionException, _explain_coordination_failure)
