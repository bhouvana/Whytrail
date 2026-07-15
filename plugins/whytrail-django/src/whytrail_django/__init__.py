"""Django integration (ADR 0002 §3 item 5, §7 Tier A).

Safe-by-default exception middleware -- the same design as
whytrail-fastapi's, adapted to Django's own conventions: old-style
middleware's `process_exception` hook, and settings.DEBUG as the
default for whether an explanation reaches the response at all.
Django already established exactly this mental model (DEBUG=True
shows a rich error page with locals; DEBUG=False shows a generic one)
decades ago; reinventing it with a different flag name would be worse
than following it.
"""

from __future__ import annotations

import logging
import typing as t

from django.http import JsonResponse

import whytrail

__version__ = "0.1.0"

_logger = logging.getLogger("whytrail.django")


class WhytrailMiddleware:
    """Add to MIDDLEWARE:

        MIDDLEWARE = [..., "whytrail_django.WhytrailMiddleware"]

    Configured via Django settings, not constructor kwargs -- Django's
    MIDDLEWARE list holds dotted paths, not instantiation calls, so
    settings are the idiomatic place for this:

        WHYTRAIL_DEBUG = False                        # default: settings.DEBUG
        WHYTRAIL_INCLUDE_LOCALS_IN_RESPONSE = False    # default: False, always
        WHYTRAIL_LOG_LOCALS = False                    # default: False, always

    Both locals opt-ins default to False regardless of WHYTRAIL_DEBUG /
    settings.DEBUG (ADR 0002 §3 item 5) -- a local variable at an
    exception's origin frame can hold a secret, and that risk doesn't
    go away just because a team runs DEBUG=True in a shared staging
    environment reachable by more than the one developer looking at
    their own terminal.
    """

    def __init__(self, get_response: t.Callable) -> None:
        self.get_response = get_response
        self.logger = _logger

    def __call__(self, request: t.Any) -> t.Any:
        return self.get_response(request)

    def process_exception(self, request: t.Any, exception: Exception) -> JsonResponse:
        from django.conf import settings

        debug = getattr(settings, "WHYTRAIL_DEBUG", getattr(settings, "DEBUG", False))
        include_locals_in_response = getattr(settings, "WHYTRAIL_INCLUDE_LOCALS_IN_RESPONSE", False)
        log_locals = getattr(settings, "WHYTRAIL_LOG_LOCALS", False)

        explanation = whytrail.why(exception)

        log_explanation = explanation if log_locals else explanation.redacted()
        self.logger.error(
            "unhandled exception on %s %s\n%s",
            request.method,
            request.path,
            log_explanation.text,
            exc_info=exception,
        )

        if not debug:
            return JsonResponse({"detail": "Internal Server Error"}, status=500)

        response_explanation = explanation if include_locals_in_response else explanation.redacted()
        return JsonResponse(
            {"detail": "Internal Server Error", "why": response_explanation.json()}, status=500
        )
