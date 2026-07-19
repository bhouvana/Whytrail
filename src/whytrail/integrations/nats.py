"""whytrail plugin for nats-py (ADR 0003).

Found while triaging this: the base `nats.errors.Error` hierarchy
(connection/timeout/protocol errors) turned out to be almost entirely
GENERIC -- every concrete class but one hardcodes its own `__str__`
with no dynamic fields at all, so there's nothing a plugin adds over
tier 1 (the same "checked, nothing to add" verdict this project has
already logged for redis-py/PyJWT/kafka-python, see ADR 0003). The one
exception, `SlowConsumerError`, already puts its structured fields
directly in its own `__str__`.

`nats.js.errors.APIError` (JetStream's own API-response error, a
different hierarchy from the base client errors above) is a real
match: it carries the JetStream API's structured response --
`.code`/`.err_code`/`.description`/`.stream`/`.seq` -- which a bare
`str(exc)` folds into one line.

`.description` goes through `locals`, not `description` (ADR 0002 §3
item 5): JetStream API error descriptions can echo back the stream or
subject name involved.
"""

from __future__ import annotations

import nats.js.errors

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_api_error(exc: "nats.js.errors.APIError") -> Explanation:
    detail_parts = []
    if exc.code is not None:
        detail_parts.append(f"code={exc.code}")
    if exc.err_code is not None:
        detail_parts.append(f"err_code={exc.err_code}")
    if exc.stream is not None:
        detail_parts.append(f"stream={exc.stream}")
    if exc.seq is not None:
        detail_parts.append(f"seq={exc.seq}")
    subject = f"{type(exc).__name__}: {', '.join(detail_parts)}" if detail_parts else type(exc).__name__
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    if exc.description:
        steps.append(
            ExplanationStep(
                description="description",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"description": exc.description},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(nats.js.errors.APIError, _explain_api_error)
