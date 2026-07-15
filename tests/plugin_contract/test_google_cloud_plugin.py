"""Validates whytrail-google-cloud against real google.api_core
exception objects -- and confirms the shared-base registration claim
(one plugin covers storage/bigquery/pubsub/etc.) by checking multiple
concrete exception classes, not just NotFound."""

from __future__ import annotations

import pytest

google_exceptions = pytest.importorskip("google.api_core.exceptions")
pytest.importorskip("whytrail_google_cloud")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

BUCKET_NAME = "my-secret-bucket"


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(google_exceptions.GoogleAPICallError) is not None


def test_why_shows_code_and_message():
    exc = google_exceptions.NotFound(f"bucket {BUCKET_NAME} not found")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "404" in explanation.text
    assert BUCKET_NAME in explanation.text  # the resource identifier, treated like a URL


def test_details_are_in_locals_and_strippable():
    exc = google_exceptions.NotFound("not found", details=["extra internal detail", "second detail"])
    explanation = whytrail.why(exc)
    step = next(s for s in explanation.steps if s.locals)
    assert "extra internal detail" in step.locals["details"]
    assert "extra internal detail" not in step.description


@pytest.mark.parametrize(
    "exc_cls,expected_code",
    [
        (google_exceptions.NotFound, 404),
        (google_exceptions.PermissionDenied, 403),
        (google_exceptions.AlreadyExists, 409),
    ],
)
def test_covers_multiple_services_error_types_via_shared_base(exc_cls, expected_code):
    """These map to different underlying services (storage 404s,
    IAM 403s, ...) but all resolve through the one registration
    against GoogleAPICallError -- confirming the "one plugin, whole
    family" claim in the module docstring, not just testing NotFound."""
    exc = exc_cls("something went wrong")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert str(expected_code) in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(google_exceptions.GoogleAPICallError, lambda exc: "overridden by the user")
    explanation = whytrail.why(google_exceptions.NotFound("x"))
    assert "overridden by the user" in explanation.text
