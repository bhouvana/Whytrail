"""Sentry SDK integration (ADR 0002 §7, Tier A).

Attaches a whytrail Explanation to every Sentry event that has an
associated exception, via Sentry's own `before_send` hook -- the
standard, documented way to enrich outgoing events. No monkeypatching,
no custom Integration subclass, no dependency on Sentry internals
beyond the public `before_send(event, hint)` contract every Sentry SDK
user already knows.
"""

from __future__ import annotations

import typing as t

import whytrail

__version__ = "0.1.0"

_CONTEXT_KEY = "whytrail"


def before_send(event: dict, hint: dict, *, include_locals: bool = False) -> dict:
    """Pass directly to sentry_sdk.init(before_send=...), or compose
    with an existing hook via chain().

        import sentry_sdk
        import whytrail_sentry

        sentry_sdk.init(dsn="...", before_send=whytrail_sentry.before_send)

    `include_locals` defaults to False: an event sent to Sentry has
    left the process, and a local variable at an exception's origin
    frame can hold a secret. Sentry's own SDK has the identical
    trade-off with its native frame-locals capture, off by default in
    most setups for exactly this reason -- whytrail-sentry follows the
    same default rather than being the looser link in the chain. Pass
    True deliberately (e.g. via functools.partial) if your Sentry
    project's access and retention policy make that acceptable.
    """
    exc_info = hint.get("exc_info")
    if not exc_info:
        return event
    exc = exc_info[1]
    if exc is None:
        return event

    explanation = whytrail.why(exc)
    if not explanation.known:
        return event
    if not include_locals:
        explanation = explanation.redacted()

    payload = explanation.json()
    contexts = event.setdefault("contexts", {})
    contexts[_CONTEXT_KEY] = {
        "subject": payload["subject"],
        "confidence": payload["confidence"],
        "text": explanation.text,
        "steps": payload["steps"],
    }
    return event


def chain(
    existing: t.Callable[[dict, dict], dict | None] | None,
) -> t.Callable[[dict, dict], dict | None]:
    """Compose whytrail's before_send with a caller's existing hook, so
    adding whytrail-sentry doesn't require giving up existing
    before_send logic.

        sentry_sdk.init(dsn="...", before_send=whytrail_sentry.chain(my_existing_hook))
    """
    if existing is None:
        return before_send

    def combined(event: dict, hint: dict) -> dict | None:
        event = existing(event, hint)
        if event is None:
            return None
        return before_send(event, hint)

    return combined
