"""whytrail plugin for confluent-kafka (the librdkafka-backed client)
(ADR 0003).

Not the same verdict as `kafka-python`, already rejected elsewhere in
this ecosystem: `kafka-python`'s `errno`/`message`/`description` are
class-level constants from a static protocol-error-code table, never
populated per-instance. `confluent_kafka.KafkaException.args[0]` is a
real, per-instance `KafkaError` object instead, confirmed directly --
`.code()`/`.name()` (a stable librdkafka error-code taxonomy, e.g.
`"_UNKNOWN_TOPIC"`) and `.fatal()`/`.retriable()` (booleans a caller
would branch retry logic on), which `str(exc)` folds into one
`KafkaError{code=...,val=...,str="..."}` line.

`.str()` (librdkafka's own message) goes through `locals`, not
`description` (ADR 0002 §3 item 5): it routinely echoes back the
offending topic/partition name. `.name()`/`.fatal()`/`.retriable()` --
a small closed taxonomy and booleans, never request content -- are
safe in `description`.
"""

from __future__ import annotations

from confluent_kafka import KafkaException

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_kafka_exception(exc: "KafkaException") -> Explanation:
    error = exc.args[0] if exc.args else None
    name = error.name() if error is not None else None
    fatal = error.fatal() if error is not None else None
    retriable = error.retriable() if error is not None else None
    message = error.str() if error is not None else None

    subject = f"{type(exc).__name__} ({name})" if name else type(exc).__name__
    desc_parts = [subject]
    if fatal is not None:
        desc_parts.append(f"fatal={fatal}")
    if retriable is not None:
        desc_parts.append(f"retriable={retriable}")
    steps = [
        ExplanationStep(
            description=", ".join(desc_parts),
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    if message:
        steps.append(
            ExplanationStep(
                description="broker message",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"message": str(message)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(KafkaException, _explain_kafka_exception)
