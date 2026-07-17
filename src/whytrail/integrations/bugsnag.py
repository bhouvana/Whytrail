"""Bugsnag integration (ADR 0003).

Attaches a why() Explanation to a Bugsnag report via
`bugsnag.notify()`'s `metadata` parameter -- the same shape as
`whytrail-newrelic`/`whytrail-rollbar`/`whytrail-elastic-apm`'s
custom-attribute pattern, and the same safe-by-default redaction
posture (ADR 0002 §3 item 5): a Bugsnag report has left the process and
is retained and searchable well beyond the person debugging right now.
"""

from __future__ import annotations

from whytrail.core.explanation import Explanation

_TAB_NAME = "whytrail"


def record(
    explanation: Explanation,
    *,
    exception: BaseException,
    include_locals: bool = False,
) -> None:
    """Report `exception` to Bugsnag with `explanation` attached as a
    metadata tab.

    `include_locals` defaults to False for the same reason as
    whytrail.otel.record: pass True deliberately only if your Bugsnag
    account's access and retention policy make that acceptable.
    """
    import bugsnag as _bugsnag

    source = explanation if include_locals else explanation.redacted()
    _bugsnag.notify(exception, metadata={_TAB_NAME: source.json()})
