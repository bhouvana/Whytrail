"""Elastic APM integration (ADR 0003).

Attaches a why() Explanation to an Elastic APM error event via
`elasticapm.Client.capture_exception()`'s `custom` parameter -- the
same shape as `whytrail-newrelic`/`whytrail-rollbar`'s custom-attribute
pattern, and the same safe-by-default redaction posture (ADR 0002 §3
item 5): an APM error event has left the process and is retained and
searchable well beyond the person debugging right now.
"""

from __future__ import annotations

import typing as t

from whytrail.core.explanation import Explanation

_KEY_PREFIX = "whytrail"


def record(
    explanation: Explanation,
    *,
    client: t.Any = None,
    include_locals: bool = False,
) -> None:
    """Report the currently handled exception to Elastic APM via
    `client` (or `elasticapm.get_client()`, if `client` is None) with
    `explanation` attached as custom context.

    `include_locals` defaults to False for the same reason as
    whytrail.otel.record: pass True deliberately only if your Elastic
    APM deployment's access and retention policy make that acceptable.
    """
    import elasticapm

    target_client = client if client is not None else elasticapm.get_client()
    if target_client is None:
        return

    source = explanation if include_locals else explanation.redacted()
    target_client.capture_exception(custom={_KEY_PREFIX: source.json()})
