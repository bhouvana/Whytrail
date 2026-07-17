"""Rollbar integration (ADR 0003).

Attaches a why() Explanation to a Rollbar report via
`rollbar.report_exc_info()`'s `extra_data` parameter -- the same shape
as `whytrail-newrelic`/`whytrail-ddtrace`'s custom-attribute pattern,
and the same safe-by-default redaction posture (ADR 0002 §3 item 5): a
Rollbar report has left the process and is retained and searchable
well beyond the person debugging right now.
"""

from __future__ import annotations

import sys
import typing as t

from whytrail.core.explanation import Explanation

_KEY_PREFIX = "whytrail"


def record(
    explanation: Explanation,
    *,
    exc_info: tuple[t.Any, t.Any, t.Any] | None = None,
    include_locals: bool = False,
) -> None:
    """Report `exc_info` (or `sys.exc_info()`, if `exc_info` is None)
    to Rollbar with `explanation` attached as extra data.

    `include_locals` defaults to False for the same reason as
    whytrail.otel.record: pass True deliberately only if your Rollbar
    account's access and retention policy make that acceptable.
    """
    import rollbar as _rollbar

    source = explanation if include_locals else explanation.redacted()
    _rollbar.report_exc_info(
        exc_info if exc_info is not None else sys.exc_info(),
        extra_data={_KEY_PREFIX: source.json()},
    )
