"""Flask integration (ADR 0002 §3 item 5, ADR 0003).

Same design as whytrail-fastapi/whytrail-django, adapted to Flask's
`errorhandler` registration: safe by default, two separate opt-ins for
the two separate questions ("should the client see an explanation at
all" and "should it include raw local variable values"), mirroring
Django's DEBUG convention rather than inventing a new mental model for
something this security-sensitive.
"""

from __future__ import annotations

import logging
import typing as t

import whytrail

__version__ = "0.1.0"

_logger = logging.getLogger("whytrail.flask")


def install(
    app: t.Any,
    *,
    debug: bool | None = None,
    include_locals_in_response: bool = False,
    log_locals: bool = False,
    logger: logging.Logger | None = None,
) -> None:
    """Wire a global exception handler into a Flask app.

        app = Flask(__name__)
        whytrail_flask.install(app)                     # production-safe default
        whytrail_flask.install(app, debug=True)          # local dev: explanation in the response, locals still redacted

    `debug` defaults to `app.debug` (Flask's own flag) when not given
    explicitly. Both locals opt-ins default to False regardless of
    debug mode (ADR 0002 §3 item 5): a local variable at an exception's
    origin frame can hold a secret, and that risk doesn't go away just
    because a team runs a shared staging environment with debug=True.
    """
    log = logger or _logger

    @app.errorhandler(Exception)
    def _handler(exc: Exception):
        from flask import jsonify, request

        explanation = whytrail.why(exc)

        log_explanation = explanation if log_locals else explanation.redacted()
        log.error(
            "unhandled exception on %s %s\n%s",
            request.method,
            request.path,
            log_explanation.text,
            exc_info=exc,
        )

        effective_debug = app.debug if debug is None else debug
        if not effective_debug:
            return jsonify({"detail": "Internal Server Error"}), 500

        response_explanation = explanation if include_locals_in_response else explanation.redacted()
        return jsonify({"detail": "Internal Server Error", "why": response_explanation.json()}), 500
