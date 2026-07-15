# whytrail-ddtrace

Attaches a `whytrail` `Explanation` to the current Datadog (ddtrace) span as
tags, so existing Datadog dashboards show whytrail's causal chain inline
with a trace already being looked at.

```python
import whytrail
import whytrail_ddtrace

try:
    risky_call()
except Exception as exc:
    explanation = whytrail.why(exc)
    whytrail_ddtrace.record(explanation)
```

**Locals are redacted by default** (ADR 0002 §3 item 5), the same posture
as `whytrail.otel`/`whytrail-sentry`: a span exported to Datadog has left the
process. Opt in explicitly if your account's retention policy makes that
acceptable:

```python
whytrail_ddtrace.record(explanation, include_locals=True)
```
