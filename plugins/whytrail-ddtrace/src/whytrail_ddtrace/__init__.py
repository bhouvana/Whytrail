"""Datadog (ddtrace) integration (ADR 0003).

Attaches a why() Explanation to the current ddtrace span as tags, the
same shape as whytrail.otel's OpenTelemetry interop (span tags instead
of span events -- ddtrace's own idiom -- but the same flattening and
the same safe-by-default redaction posture, ADR 0002 §3 item 5): a
span exported to Datadog has left the process and is often retained
and searchable well beyond the person debugging right now.
"""

from __future__ import annotations

import typing as t

from whytrail.core.explanation import Explanation

__version__ = "0.1.0"

_TAG_PREFIX = "whytrail."


def record(explanation: Explanation, *, span: t.Any = None, include_locals: bool = False) -> bool:
    """Attach `explanation` to `span` (or the current active span, if
    any) as tags. Returns False, without raising, if there's no active
    span -- recording provenance must never break the surrounding
    request just because tracing wasn't configured for this call path.

    `include_locals` defaults to False for the same reason as
    whytrail.otel.record: pass True deliberately if your Datadog
    account's access and retention policy make that acceptable.
    """
    from ddtrace.trace import tracer

    target_span = span if span is not None else tracer.current_span()
    if target_span is None:
        return False

    source = explanation if include_locals else explanation.redacted()
    tags = _flatten_tags(source.json(), prefix=_TAG_PREFIX)
    target_span.set_tags(tags)
    return True


def _flatten_tags(payload: dict[str, t.Any], *, prefix: str) -> dict[str, str]:
    flat: dict[str, str] = {}
    for key, value in payload.items():
        full_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten_tags(value, prefix=f"{full_key}."))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                if isinstance(item, dict):
                    flat.update(_flatten_tags(item, prefix=f"{full_key}.{i}."))
                else:
                    flat[f"{full_key}.{i}"] = _scalar(item)
        else:
            flat[full_key] = _scalar(value)
    return flat


def _scalar(value: t.Any) -> str:
    if value is None:
        return ""
    return str(value)
