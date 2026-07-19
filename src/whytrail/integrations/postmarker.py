"""whytrail plugin for postmarker, the Postmark email SDK (ADR 0003).

`ClientError` carries Postmark's own documented numeric `.error_code`
taxonomy (each code mapped to a specific meaning at postmarkapp.com/
developer/api/overview#error-codes) -- one field, but a real one a
bare `str(exc)` doesn't expose separately, the same "one field" bar
`whytrail[pyzmq]`/`whytrail[algoliasearch]` already clear.
"""

from __future__ import annotations

import postmarker.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_client_error(exc: "postmarker.exceptions.ClientError") -> Explanation:
    subject = f"{type(exc).__name__}: error_code={exc.error_code}"
    steps = [ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external")]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(postmarker.exceptions.ClientError, _explain_client_error)
