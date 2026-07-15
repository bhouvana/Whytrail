# whytrail-sentry

Attaches a `whytrail` explanation to every Sentry event that has an
associated exception -- Sentry already shows you the traceback and
breadcrumbs; this adds the causal chain (`__cause__`/`__context__`, or a
tracked value's provenance) as a structured context block next to them.

```python
import sentry_sdk
import whytrail_sentry

sentry_sdk.init(dsn="...", before_send=whytrail_sentry.before_send)

# already using before_send for something else?
sentry_sdk.init(dsn="...", before_send=whytrail_sentry.chain(my_existing_hook))
```

Uses Sentry's standard, documented `before_send` hook -- no monkeypatching,
no custom `Integration` subclass.

**Local variables are redacted by default.** An event sent to Sentry has
left your process, and a local variable at an exception's origin frame
can hold a secret. Opt in explicitly if your project's retention policy
makes that acceptable:

```python
import functools
sentry_sdk.init(dsn="...", before_send=functools.partial(whytrail_sentry.before_send, include_locals=True))
```
