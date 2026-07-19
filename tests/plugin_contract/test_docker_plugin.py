"""Validates whytrail's docker plugin against a real
docker.errors.APIError wrapping a real requests.Response -- no live
Docker daemon needed."""

from __future__ import annotations

import pytest

docker = pytest.importorskip("docker")
requests = pytest.importorskip("requests")
pytest.importorskip("whytrail.integrations.docker")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from docker.errors import APIError  # noqa: E402

SECRET_CONTAINER = "my-secret-prod-container"


def _api_error(explanation=None):
    response = requests.Response()
    response.status_code = 409
    return APIError(
        "409 Client Error",
        response=response,
        explanation=explanation if explanation is not None else f"conflict: container {SECRET_CONTAINER} already in use",
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(APIError) is not None


def test_why_on_api_error_shows_status():
    explanation = whytrail.why(_api_error())
    assert explanation.known
    assert "409" in explanation.text


def test_explanation_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_CONTAINER in detail_step.locals["explanation"]
    assert SECRET_CONTAINER not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_CONTAINER not in redacted.text
    assert "409" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(APIError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_error())
    assert "overridden by the user" in explanation.text
