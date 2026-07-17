"""Honeybadger integration (ADR 0003).

Attaches a why() Explanation to a Honeybadger notification via
`honeybadger.honeybadger.notify()`'s `context` parameter -- the same
shape as `whytrail-newrelic`/`whytrail-rollbar`'s custom-attribute
pattern, and the same safe-by-default redaction posture (ADR 0002 §3
item 5): a Honeybadger notification has left the process and is
retained and searchable well beyond the person debugging right now.
"""

from __future__ import annotations

from whytrail.core.explanation import Explanation

_KEY_PREFIX = "whytrail"


def record(
    explanation: Explanation,
    *,
    exception: BaseException | None = None,
    include_locals: bool = False,
) -> None:
    """Notify Honeybadger of `exception` (or the currently handled
    exception, if `exception` is None) with `explanation` attached as
    context.

    `include_locals` defaults to False for the same reason as
    whytrail.otel.record: pass True deliberately only if your
    Honeybadger account's access and retention policy make that
    acceptable.
    """
    import honeybadger as _honeybadger

    source = explanation if include_locals else explanation.redacted()
    _honeybadger.honeybadger.notify(exception=exception, context={_KEY_PREFIX: source.json()})
