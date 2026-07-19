"""whytrail plugin for python-arango, the ArangoDB driver (ADR 0003).

`ArangoServerError` carries the HTTP status, ArangoDB's own numeric
`.error_code` (from its documented error-code taxonomy), the request
URL/method, and headers -- detail a bare `str(exc)` only shows folded
into one pre-formatted line.

Found while building this: `.message` is that same pre-formatted
string (`ArangoServerError.__init__` builds it as `f"[HTTP {code}][ERR
{error_code}] {msg}"` and assigns it to both `.message` and the
exception's own `args`), so it -- and `.error_message`/`.url`, which
can reference the specific collection/document/query involved -- go
through `locals`, not `description` (ADR 0002 §3 item 5), same
reasoning as the `square`/`mistralai` plugins' own "don't reuse the
pre-built message string" finding.
"""

from __future__ import annotations

import arango.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_server_error(exc: "arango.exceptions.ArangoServerError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.http_code} (ArangoDB error {exc.error_code})"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.error_message or "", "url": exc.url or ""},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(arango.exceptions.ArangoServerError, _explain_server_error)
