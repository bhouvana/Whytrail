"""whytrail plugin for hvac, the HashiCorp Vault client (ADR 0003).

`VaultError` (and its per-status subclasses -- `InvalidRequest`,
`Forbidden`, `RateLimitExceeded`, ...) carries Vault's own structured
`errors` list, the HTTP method/URL, and the raw response text/JSON --
detail `str(exc)` collapses into one line.

Every field here goes through `locals`, not `description` (ADR 0002 §3
item 5), more aggressively than most other integrations: `.url` is a
Vault *path*, which routinely encodes the secret's own name (e.g.
`secret/data/prod/db-password`), not just an identifier -- there's no
safe subset of this exception's fields the way there is with e.g. an
HTTP status code, so the subject stays limited to the exception's own
type name (which already communicates the failure class via Vault's
status-code-to-exception-class mapping -- `Forbidden`, `InvalidPath`,
`RateLimitExceeded`, etc.).
"""

from __future__ import annotations

import hvac.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_vault_error(exc: "hvac.exceptions.VaultError") -> Explanation:
    subject = type(exc).__name__
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={
                "method": exc.method or "",
                "url": exc.url or "",
                "errors": repr(exc.errors) if exc.errors else "",
            },
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(hvac.exceptions.VaultError, _explain_vault_error)
