"""whytrail plugin for dramatiq (ADR 0003).

Registers a `dramatiq.Middleware` implementing `after_process_message`
-- dramatiq's own hook for observing every actor run's outcome,
success or failure -- and logs a whytrail explanation, including the
message's args/kwargs, when `exception` is set. Same shape as
whytrail-celery/whytrail-rq, adapted to dramatiq's middleware protocol
instead of a signal or handler chain.

Message args/kwargs go through the same locals-style redaction as
everywhere else in this ecosystem (ADR 0002 §3 item 5).
"""

from __future__ import annotations

import logging
import typing as t

import dramatiq

import whytrail
from whytrail import Confidence, ExplanationStep

__version__ = "0.1.0"

_logger = logging.getLogger("whytrail.dramatiq")


class WhytrailMiddleware(dramatiq.Middleware):
    def __init__(self, *, log_locals: bool = False, logger: logging.Logger | None = None) -> None:
        self.log_locals = log_locals
        self.logger = logger or _logger

    def after_process_message(
        self,
        broker: "dramatiq.Broker",
        message: "dramatiq.MessageProxy",
        *,
        result: t.Any = None,
        exception: BaseException | None = None,
    ) -> None:
        if exception is None:
            return
        explanation = whytrail.why(exception)
        if explanation.known:
            explanation.steps.append(
                ExplanationStep(
                    description=f"actor {message.actor_name!r} invoked with these arguments",
                    confidence=Confidence.EXPLICIT.value,
                    kind="call",
                    locals=_args_as_dict(message.args, message.kwargs),
                )
            )
        log_explanation = explanation if self.log_locals else explanation.redacted()
        self.logger.error(
            "actor %s (message_id=%s) failed\n%s", message.actor_name, message.message_id, log_explanation.text
        )


def install(broker: "dramatiq.Broker", *, log_locals: bool = False, logger: logging.Logger | None = None) -> None:
    """Add the middleware to a broker.

        broker = RabbitmqBroker(...)
        dramatiq.set_broker(broker)
        import whytrail_dramatiq
        whytrail_dramatiq.install(broker)
    """
    broker.add_middleware(WhytrailMiddleware(log_locals=log_locals, logger=logger))


def _args_as_dict(args: t.Any, kwargs: t.Any) -> dict[str, str] | None:
    result: dict[str, str] = {}
    for i, value in enumerate(args or ()):
        result[f"args[{i}]"] = repr(value)
    for key, value in (kwargs or {}).items():
        result[f"kwargs[{key}]"] = repr(value)
    return result or None
