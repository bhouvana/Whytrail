"""FastAPI/Starlette integration (ADR 0002 §3 item 5, §7 Tier A).

This is the integration the strategy review specifically called out as
not allowed to ship until the underlying safety question was resolved:
tier-1's locals capture is exactly right for local dev and exactly
wrong to expose unmodified in a production HTTP response, since a
local variable at an exception's origin frame can trivially hold a
password, an API key, or a customer record. Everything below is safe
by default and requires an explicit, separate opt-in for each of the
two places detail could leak (the HTTP response and the server log),
mirroring Django's DEBUG flag rather than inventing a new mental model
for something this security-sensitive.
"""

from __future__ import annotations

import logging
import typing as t

from starlette.requests import Request
from starlette.responses import JSONResponse

import whytrail

_logger = logging.getLogger("whytrail.fastapi")


def install(
    app: t.Any,
    *,
    debug: bool = False,
    include_locals_in_response: bool = False,
    log_locals: bool = False,
    logger: logging.Logger | None = None,
) -> None:
    """Wire a global exception handler into a FastAPI/Starlette app.

        from whytrail.integrations import fastapi as whytrail_fastapi

        app = FastAPI()
        whytrail_fastapi.install(app)                    # production-safe default
        whytrail_fastapi.install(app, debug=True)         # local dev: explanation in the response, locals still redacted
        whytrail_fastapi.install(app, debug=True, include_locals_in_response=True)  # local dev only, be sure

    Defaults, all safe:
      - `debug=False`: the HTTP response is a generic 500 with no
        explanation detail at all -- whoever made the request is not
        automatically someone who should see internal state.
      - Even with `debug=True`, locals are redacted from the response
        unless `include_locals_in_response=True` is *also* set --
        two separate opt-ins for two separate questions ("should the
        client see an explanation at all" and "should it include raw
        local variable values").
      - The server-side log line is redacted too, unless
        `log_locals=True`. Logs get shipped to aggregators and SIEMs
        more often than a team plans for when `logging.error()` is
        first added; the safe default follows the data, not the
        assumption that "it's just a server log."
    """
    log = logger or _logger

    async def handler(request: Request, exc: Exception) -> JSONResponse:
        explanation = whytrail.why(exc)

        log_explanation = explanation if log_locals else explanation.redacted()
        log.error(
            "unhandled exception on %s %s\n%s",
            request.method,
            request.url.path,
            log_explanation.text,
            exc_info=exc,
        )

        if not debug:
            return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

        response_explanation = explanation if include_locals_in_response else explanation.redacted()
        return JSONResponse(
            {"detail": "Internal Server Error", "why": response_explanation.json()},
            status_code=500,
        )

    app.add_exception_handler(Exception, handler)
