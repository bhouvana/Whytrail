"""whytrail plugin for the Auth0 Python SDK (ADR 0003).

Two distinct exception hierarchies, registered separately -- Auth0's
SDK splits its Authentication API (login, token exchange) from its
Management API (users, tenants, ...) into separate client modules with
their own error types, confirmed by reading both rather than assumed
from one:

- `auth0.authentication.exceptions.Auth0Error`: `.status_code`,
  `.error_code`, `.message`, `.content` (the raw response body).
- `auth0.management.core.api_error.ApiError`: `.status_code`,
  `.headers`, `.body` -- the generated-OpenAPI-client shape also used
  by `whytrail[pinecone]`/`whytrail[plaid]`.

`.message`/`.content`/`.body` go through `locals`, not `description`
(ADR 0002 §3 item 5): an auth error's body routinely echoes back the
client ID, connection name, or (for a failed login) part of the
credential that was rejected.
"""

from __future__ import annotations

import auth0.authentication.exceptions
import auth0.management.core.api_error

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_authentication_error(exc: "auth0.authentication.exceptions.Auth0Error") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}" + (f" ({exc.error_code})" if exc.error_code else "")
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description="response detail",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.message, "content": repr(exc.content)} if exc.content else {"message": exc.message},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def _explain_management_api_error(exc: "auth0.management.core.api_error.ApiError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    if exc.body is not None:
        steps.append(
            ExplanationStep(
                description="response body",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals={"body": repr(exc.body)},
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(auth0.authentication.exceptions.Auth0Error, _explain_authentication_error)
    register_from_plugin(auth0.management.core.api_error.ApiError, _explain_management_api_error)
