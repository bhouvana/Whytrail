"""whytrail plugin for MLflow (ADR 0003).

`MlflowException` carries a closed, documented error-code taxonomy
(`.error_code`, e.g. `INVALID_PARAMETER_VALUE`/`RESOURCE_DOES_NOT_EXIST`),
a derived `.error_class`, an optional `.sqlstate` for backend-store
errors, and `.get_http_status_code()` -- detail a bare `str(exc)`
(just the message) drops entirely.

`.message` goes through `locals`, not `description` (ADR 0002 §3 item
5): it routinely references the specific run ID, experiment name, or
artifact path involved.
"""

from __future__ import annotations

import mlflow.exceptions

from whytrail import Confidence, Explanation, ExplanationStep
from whytrail.registry import register_from_plugin


def _explain_mlflow_exception(exc: "mlflow.exceptions.MlflowException") -> Explanation:
    # mlflow ships py.typed but leaves get_http_status_code() itself
    # untyped -- a real, narrower gap than the whole-module
    # ignore_missing_imports entries elsewhere in this ecosystem
    # (twilio, plaid, ...), so a targeted ignore here instead of adding
    # mlflow to that list, which would also suppress real strict-mode
    # findings in the rest of this file.
    status_code = exc.get_http_status_code()  # type: ignore[no-untyped-call]
    subject = f"{type(exc).__name__}: {exc.error_code} (HTTP {status_code})"
    detail_parts = []
    if exc.error_class:
        detail_parts.append(f"error_class={exc.error_class}")
    if exc.sqlstate:
        detail_parts.append(f"sqlstate={exc.sqlstate}")
    steps = [
        ExplanationStep(description=subject, confidence=Confidence.EXPLICIT.value, kind="external"),
        ExplanationStep(
            description=", ".join(detail_parts) if detail_parts else "message",
            confidence=Confidence.EXPLICIT.value,
            kind="external",
            locals={"message": exc.message},
        ),
    ]
    return Explanation(subject=subject, steps=steps, tracked=True)


def register() -> None:
    register_from_plugin(mlflow.exceptions.MlflowException, _explain_mlflow_exception)
