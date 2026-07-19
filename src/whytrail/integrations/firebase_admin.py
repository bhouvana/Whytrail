"""whytrail plugin for the Firebase Admin SDK (ADR 0003).

`FirebaseError` carries a canonical error `.code` (the Google Cloud API
error-code taxonomy, e.g. `NOT_FOUND`/`PERMISSION_DENIED`), the
original `.cause` exception when the error wraps a lower-level one, and
the raw `.http_response` when it came from an HTTP call -- detail a
bare `str(exc)` (just the message) drops entirely.

The message and any wrapped `.cause` go through `locals`, not
`description` (ADR 0002 §3 item 5): both can reference the specific
user record, document path, or token involved.
"""

from __future__ import annotations

import firebase_admin.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_firebase_error(exc: "firebase_admin.exceptions.FirebaseError") -> Explanation:
    subject = f"{type(exc).__name__}: {exc.code}"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": str(exc), "cause": repr(exc.cause)} if exc.cause is not None else {"message": str(exc)},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(firebase_admin.exceptions.FirebaseError, _explain_firebase_error)
