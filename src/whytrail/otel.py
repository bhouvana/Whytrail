"""OpenTelemetry span interop (ADR §14 -- the buildable slice of
v3.0).

Attaches a why() Explanation to the current OTel span as an event, so
existing OTel tooling (Jaeger, Tempo, whatever dashboard a team
already has open) can see whytrail's causal chain inline with the trace
they're already looking at, instead of it living in a separate tool.

Requires the `otel` extra: pip install whytrail[otel]. whytrail's core has
zero required dependencies (ADR §17); importing this module without
the extra installed raises a clear ImportError rather than a cryptic
one, but whytrail itself never imports it implicitly.
"""

from __future__ import annotations

import typing as t

from .core.explanation import Explanation

_EVENT_NAME = "whytrail.explanation"


def _require_otel() -> t.Any:
    try:
        from opentelemetry import trace
    except ImportError as exc:  # pragma: no cover - exercised only without the extra installed
        raise ImportError(
            "OpenTelemetry interop needs the 'otel' extra: pip install whytrail[otel]"
        ) from exc
    return trace


def record(explanation: Explanation, *, span: t.Any = None, include_locals: bool = False) -> bool:
    """Attach `explanation` to `span` (or the current active span, if
    any) as an event. Returns False, without raising, if there's no
    recording span to attach to -- recording provenance must never
    break the surrounding request just because tracing wasn't
    configured for this call path.

    `include_locals` defaults to False: a span exported to an OTel
    backend (Jaeger, Honeycomb, Datadog, ...) has left the process and
    is often retained and searchable by people beyond whoever is
    debugging right now, and a local variable at an exception's origin
    frame can hold a secret. Pass True deliberately if the backend and
    retention policy are known to be safe for that (ADR 0002 §3 item 5).
    """
    trace = _require_otel()
    target_span = span if span is not None else trace.get_current_span()
    if target_span is None or not target_span.is_recording():
        return False
    source = explanation if include_locals else explanation.redacted()
    attributes = _flatten_attributes(source.json())
    target_span.add_event(_EVENT_NAME, attributes=attributes)
    return True


def _flatten_attributes(payload: dict[str, t.Any], *, prefix: str = "") -> dict[str, t.Any]:
    """OTel span event attributes must be primitives or homogeneous
    sequences of primitives -- flatten whytrail's nested Explanation
    JSON into that shape rather than silently dropping the nested
    parts."""
    flat: dict[str, t.Any] = {}
    for key, value in payload.items():
        full_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten_attributes(value, prefix=f"{full_key}."))
        elif isinstance(value, list):
            if any(isinstance(v, dict) for v in value):
                for i, item in enumerate(value):
                    if isinstance(item, dict):
                        flat.update(_flatten_attributes(item, prefix=f"{full_key}.{i}."))
                    else:
                        flat[f"{full_key}.{i}"] = _scalar(item)
            else:
                flat[full_key] = [_scalar(v) for v in value]
        else:
            flat[full_key] = _scalar(value)
    return flat


def _scalar(value: t.Any) -> t.Any:
    if value is None:
        return ""
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)
