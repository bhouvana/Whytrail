"""whytrail plugin for zeep (SOAP client) (ADR 0003).

`zeep.exceptions.Fault` carries `.code`/`.actor`/`.detail`/`.subcodes`
-- the SOAP fault envelope's own structured fields, which `str(exc)`
reduces to the message alone. `.code` is a stable SOAP fault-code
taxonomy (e.g. `"Client"`/`"Server"`), safe in `description`.

`.message`/`.detail` go through `locals`, not `description` (ADR 0002
§3 item 5): a SOAP fault's message/detail routinely echoes back the
offending request field verbatim (SOAP faults commonly embed the raw
XML that triggered them).
"""

from __future__ import annotations

import zeep.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_fault(exc: "zeep.exceptions.Fault") -> Explanation:
    code = exc.code
    subject = f"{type(exc).__name__} ({code})" if code else type(exc).__name__
    steps = [
        ExplanationStep(
            description=subject,
            confidence=Confidence.EXPLICIT.value,
            kind="exception",
        )
    ]
    locals_dict = {}
    if exc.message:
        locals_dict["message"] = str(exc.message)
    if exc.detail is not None:
        locals_dict["detail"] = str(exc.detail)
    if locals_dict:
        steps.append(
            ExplanationStep(
                description="fault detail",
                confidence=Confidence.EXPLICIT.value,
                kind="external",
                locals=locals_dict,
            )
        )
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(zeep.exceptions.Fault, _explain_fault)
