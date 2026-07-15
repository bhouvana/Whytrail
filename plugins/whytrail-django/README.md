# whytrail-django

A `process_exception` middleware that logs a `whytrail` explanation
server-side on every unhandled exception.

```python
# settings.py
MIDDLEWARE = [
    ...,
    "whytrail_django.WhytrailMiddleware",
]
```

**Safe by default, on purpose** -- same reasoning as `whytrail-fastapi`. Out
of the box, the HTTP response is a generic `500 {"detail": "Internal
Server Error"}` and the server log has locals redacted, regardless of
`settings.DEBUG`.

Configured via settings, not constructor arguments (Django's `MIDDLEWARE`
list holds dotted paths, not instantiation calls):

```python
WHYTRAIL_DEBUG = True                          # default: settings.DEBUG -- include the explanation in the response
WHYTRAIL_INCLUDE_LOCALS_IN_RESPONSE = True      # default: False, always -- also include raw locals in the response
WHYTRAIL_LOG_LOCALS = True                      # default: False, always -- also include raw locals in the server log
```

`WHYTRAIL_INCLUDE_LOCALS_IN_RESPONSE` stays `False` even under
`DEBUG = True` unless set explicitly -- a shared staging environment with
`DEBUG = True` is still reachable by more than the one developer at their
own terminal.
