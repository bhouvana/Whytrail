"""Validates whytrail's mlflow plugin against a real
mlflow.exceptions.MlflowException -- no live MLflow tracking server
needed."""

from __future__ import annotations

import pytest

mlflow = pytest.importorskip("mlflow")
pytest.importorskip("whytrail.integrations.mlflow")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from mlflow.exceptions import MlflowException, RESOURCE_DOES_NOT_EXIST  # noqa: E402

SECRET_EXPERIMENT = "secret-customer-churn-experiment"


def _mlflow_exception(message=None):
    return MlflowException(
        message if message is not None else f"experiment not found: {SECRET_EXPERIMENT}",
        error_code=RESOURCE_DOES_NOT_EXIST,
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(MlflowException) is not None


def test_why_on_mlflow_exception_shows_error_code_and_http_status():
    explanation = whytrail.why(_mlflow_exception())
    assert explanation.known
    assert "RESOURCE_DOES_NOT_EXIST" in explanation.text
    assert "404" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_mlflow_exception())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_EXPERIMENT in detail_step.locals["message"]
    assert SECRET_EXPERIMENT not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_EXPERIMENT not in redacted.text
    assert "RESOURCE_DOES_NOT_EXIST" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(MlflowException, lambda exc: "overridden by the user")
    explanation = whytrail.why(_mlflow_exception())
    assert "overridden by the user" in explanation.text
