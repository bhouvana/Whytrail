"""whytrail plugin for the Twilio SDK (ADR 0003).

`TwilioRestException` carries the HTTP status, the request URI/method,
and Twilio's own numeric error code (documented per-code at
twilio.com/docs/errors/<code>) -- detail that `str(exc)` folds into a
single ANSI-colored paragraph meant for a terminal, not for `why()`'s
own step-based rendering.

`.msg`/`.details` go through `locals`, not `description` (ADR 0002 §3
item 5): Twilio's own error messages routinely echo back the phone
number, message body, or account SID that triggered the error.
"""

from __future__ import annotations

import twilio.base.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_rest_exception(exc: "twilio.base.exceptions.TwilioRestException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status}" + (f" (Twilio code {exc.code})" if exc.code else "")
    # The request URI carries the account SID -- not a secret by
    # itself, but an account identifier, so it stays out of the
    # unredactable `description` alongside the actual message/details
    # (which can echo a phone number or message body) rather than
    # judging it safe enough to be the one exception.
    request_locals = {"method": exc.method, "uri": exc.uri, "msg": exc.msg}
    if exc.details:
        request_locals["details"] = repr(exc.details)
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description="request detail",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals=request_locals,
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(twilio.base.exceptions.TwilioRestException, _explain_rest_exception)
