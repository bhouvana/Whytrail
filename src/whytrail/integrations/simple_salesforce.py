"""whytrail plugin for simple-salesforce (ADR 0003).

`SalesforceError` (the shared base of every simple-salesforce
exception -- confirmed one unified class, unlike the fragmented
per-object-type generated clients some other CRM SDKs ship) carries
the HTTP status, the specific Salesforce resource/URL queried, and the
raw response content -- detail a bare `str(exc)` folds into one
templated line.

`.content`/`.url` go through `locals`, not `description` (ADR 0002 §3
item 5): a Salesforce error response routinely echoes back the record
ID or field value that caused the failure.
"""

from __future__ import annotations

import simple_salesforce.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_salesforce_error(exc: "simple_salesforce.exceptions.SalesforceError") -> Explanation:
    subject = f"{type(exc).__name__}: HTTP {exc.status}" + (f" ({exc.resource_name})" if exc.resource_name else "")
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"url": exc.url, "content": repr(exc.content)},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(simple_salesforce.exceptions.SalesforceError, _explain_salesforce_error)
