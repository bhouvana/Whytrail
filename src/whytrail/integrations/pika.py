"""whytrail plugin for the pika AMQP/RabbitMQ client (ADR 0003).

`pika.exceptions.ChannelClosed` and `ConnectionClosed` (covering
`ChannelClosedByBroker`/`ChannelClosedByClient` and
`ConnectionClosedByBroker`/`ConnectionClosedByClient`) carry the
broker's own AMQP reply code and reply text -- e.g. `404, "NOT_FOUND -
no exchange 'orders' in vhost '/'"` -- collapsed by `str(exc)` into a
single repr line. `reply_code`/`reply_text` are properties reading
`self.args`, not instance `__dict__` entries (`vars(exc)` alone would
miss them), so this reads them the normal way, via attribute access,
not by inspecting `__dict__`.

The two classes are siblings under `pika.exceptions.AMQPError`, not
one a subclass of the other -- `ChannelClosed` has no `reply_code`
until you're inside it or `ConnectionClosed`, so both need their own
registration even though they share the exact same shape.

`reply_text` goes through `locals`, not `description` (ADR 0002 §3
item 5): a broker's reply text can echo back a queue/exchange/routing
key name from the request that shouldn't cross a process boundary
unredacted by default. `reply_code` (a small closed set of AMQP status
codes, not request content) stays in `description`.
"""

from __future__ import annotations

import pika.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_closed(exc: "pika.exceptions.ChannelClosed | pika.exceptions.ConnectionClosed") -> Explanation:
    steps = [
        ExplanationStep(
            description=f"{type(exc).__name__}: AMQP channel/connection closed",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
        )
    ]
    reply_code = getattr(exc, "reply_code", None)
    reply_text = getattr(exc, "reply_text", None)
    if reply_code is not None or reply_text is not None:
        steps.append(
            ExplanationStep(
                description=f"reply_code={reply_code}" if reply_code is not None else "broker reply",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"reply_text": str(reply_text)} if reply_text is not None else None,
            )
        )
    subject = f"{type(exc).__name__}: reply_code={reply_code}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(pika.exceptions.ChannelClosed, _explain_closed)
    register_from_plugin(pika.exceptions.ConnectionClosed, _explain_closed)
