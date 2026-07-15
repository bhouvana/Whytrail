# whytrail-fastapi

A global exception handler for FastAPI/Starlette that logs a `whytrail`
explanation server-side on every unhandled exception.

```python
from fastapi import FastAPI
import whytrail_fastapi

app = FastAPI()
whytrail_fastapi.install(app)
```

**Safe by default, on purpose.** A local variable at an exception's origin
frame can hold a password, an API key, or a customer record. Out of the
box:

- The HTTP response is a generic `500 {"detail": "Internal Server Error"}`
  -- no explanation detail at all reaches the client.
- The server-side log line has locals redacted too.

Turn on richer detail deliberately, one boundary at a time:

```python
# local dev: explanation included in the response, locals still redacted
whytrail_fastapi.install(app, debug=True)

# local dev only -- be sure: raw locals in the HTTP response
whytrail_fastapi.install(app, debug=True, include_locals_in_response=True)

# raw locals in the server log (make sure you know where your logs end up)
whytrail_fastapi.install(app, log_locals=True)
```

Never run `include_locals_in_response=True` against a deployment real
users can reach.
