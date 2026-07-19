"""whytrail plugin for the Algolia SDK (ADR 0003).

`RequestException` carries the HTTP status code separately from the
message -- a bare `str(exc)` shows the message, but not in a form a
caller can branch on programmatically; `.status_code` is that, the
same "one field, but a real one" bar `whytrail[pyzmq]` already clears
for its own `errno`.

`.message` goes through `locals`, not `description` (ADR 0002 §3 item
5): Algolia error messages routinely echo back the index name or
object ID involved.
"""

from __future__ import annotations

import algoliasearch.http.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_request_exception(exc: "algoliasearch.http.exceptions.RequestException") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status_code}"
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.message},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(algoliasearch.http.exceptions.RequestException, _explain_request_exception)
