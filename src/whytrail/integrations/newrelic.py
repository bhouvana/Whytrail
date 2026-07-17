"""New Relic integration (ADR 0003).

Attaches a why() Explanation to a New Relic error event via
`newrelic.agent.notice_error()`'s `attributes` parameter -- the same
shape as `whytrail.otel`/`whytrail-ddtrace`'s span-attachment pattern,
and the same safe-by-default redaction posture (ADR 0002 §3 item 5): a
New Relic error event has left the process and is retained and
searchable well beyond the person debugging right now.
"""

from __future__ import annotations

import typing as t

from whytrail.core.explanation import Explanation

_ATTR_PREFIX = "whytrail."


def record(
    explanation: Explanation,
    *,
    error: BaseException | None = None,
    include_locals: bool = False,
) -> None:
    """Report `error` (or the currently handled exception, if `error`
    is None) to New Relic with `explanation` attached as custom
    attributes.

    `include_locals` defaults to False for the same reason as
    whytrail.otel.record: pass True deliberately only if your New
    Relic account's access and retention policy make that acceptable.
    """
    import newrelic.agent

    source = explanation if include_locals else explanation.redacted()
    attributes = _flatten_attributes(source.json(), prefix=_ATTR_PREFIX)
    newrelic.agent.notice_error(error=error, attributes=attributes)


def _flatten_attributes(payload: dict[str, t.Any], *, prefix: str) -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in payload.items():
        full_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten_attributes(value, prefix=f"{full_key}."))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    flat.update(_flatten_attributes(item, prefix=f"{full_key}.{i}."))
                else:
                    flat[f"{full_key}.{i}"] = _scalar(item)
        else:
            flat[full_key] = _scalar(value)
    return flat


def _scalar(value: t.Any) -> str:
    if value is None:
        return ""
    return str(value)
