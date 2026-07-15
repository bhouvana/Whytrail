# whytrail-flask

A global exception handler for Flask that logs a `whytrail` explanation
server-side on every unhandled exception.

```python
from flask import Flask
import whytrail_flask

app = Flask(__name__)
whytrail_flask.install(app)
```

**Safe by default, on purpose** -- same reasoning as `whytrail-fastapi`/
`whytrail-django`. Out of the box, the HTTP response is a generic
`500 {"detail": "Internal Server Error"}` and the server log has locals
redacted, regardless of `app.debug`.

```python
whytrail_flask.install(app, debug=True)                                     # explanation in the response, locals still redacted
whytrail_flask.install(app, debug=True, include_locals_in_response=True)    # local dev only -- be sure
whytrail_flask.install(app, log_locals=True)                                 # raw locals in the server log
```

Never run `include_locals_in_response=True` against a deployment real
users can reach.
