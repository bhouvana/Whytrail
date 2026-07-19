"""aiohttp server-side (`aiohttp.web`) integration (ADR 0002 §3 item 5,
ADR 0003).

Distinct from `whytrail[aiohttp]` (the already-bundled *client*-side
explainer for `ClientResponseError`/`ClientConnectionError`): this is
the server-side middleware shape, the same safety-critical boundary
`whytrail[fastapi]`/`whytrail[django]`/`whytrail[flask]` already cover
-- named as its own candidate in ADR 0003's original triage ("Same
safety pattern, lower usage share"). Same design as those three: safe
by default, two separate opt-ins for the two separate questions
("should the client see an explanation at all" and "should it include
raw local variable values").
"""

from __future__ import annotations

import logging
import typing as t

import whytrail

_logger = logging.getLogger("whytrail.aiohttp_server")


def install(
    app: t.Any,
    *,
    debug: bool = False,
    include_locals_in_response: bool = False,
    log_locals: bool = False,
    logger: logging.Logger | None = None,
) -> None:
    """Append a global exception-handling middleware to an aiohttp.web
    Application.

        from aiohttp import web
        from whytrail.integrations import aiohttp_server as whytrail_aiohttp

        app = web.Application()
        whytrail_aiohttp.install(app)                 # production-safe default
        whytrail_aiohttp.install(app, debug=True)      # local dev: explanation in the response, locals still redacted

    `debug` defaults to False, unlike Flask's own `app.debug` fallback
    -- aiohttp's `Application` has no equivalent built-in flag to read,
    so there's nothing to default from. Both locals opt-ins default to
    False regardless of `debug` (ADR 0002 §3 item 5): a local variable
    at an exception's origin frame can hold a secret, and that risk
    doesn't go away just because a team runs a shared staging
    environment with debug=True.
    """
    from aiohttp import web

    log = logger or _logger

    from aiohttp.typedefs import Handler

    @web.middleware
    async def _middleware(request: "web.Request", handler: Handler) -> "web.StreamResponse":
        try:
            return await handler(request)
        except web.HTTPException:
            # aiohttp's own HTTP-level responses (404, redirects, ...)
            # aren't application failures -- let them through unchanged,
            # the same way whytrail-fastapi lets Starlette's own
            # HTTPException pass through untouched.
            raise
        except Exception as exc:
            explanation = whytrail.why(exc)

            log_explanation = explanation if log_locals else explanation.redacted()
            log.error(
                "unhandled exception on %s %s\n%s",
                request.method,
                request.path,
                log_explanation.text,
                exc_info=exc,
            )

            if not debug:
                return web.json_response({"detail": "Internal Server Error"}, status=500)

            response_explanation = explanation if include_locals_in_response else explanation.redacted()
            return web.json_response(
                {"detail": "Internal Server Error", "why": response_explanation.json()}, status=500
            )

    app.middlewares.append(_middleware)
