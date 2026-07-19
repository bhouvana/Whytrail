"""Validates whytrail's minio plugin against real minio.error.S3Error
objects -- no live MinIO/S3 server needed."""

from __future__ import annotations

import pytest

minio = pytest.importorskip("minio")
pytest.importorskip("whytrail.integrations.minio")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from minio.error import S3Error  # noqa: E402

SECRET_OBJECT = "customer-records/2026-secret.csv"


def _s3_error(object_name=None):
    return S3Error(
        response=None,
        code="NoSuchKey",
        message="The specified key does not exist.",
        resource="/my-bucket/" + (object_name or SECRET_OBJECT),
        request_id="16D9F5B0F7B8C1A2",
        host_id="host-id-123",
        bucket_name="my-bucket",
        object_name=object_name or SECRET_OBJECT,
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(S3Error) is not None


def test_why_on_s3_error_shows_code():
    explanation = whytrail.why(_s3_error())
    assert explanation.known
    assert "NoSuchKey" in explanation.text


def test_object_name_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_s3_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_OBJECT in detail_step.locals["object_name"]
    assert SECRET_OBJECT not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_OBJECT not in redacted.text
    assert "NoSuchKey" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(S3Error, lambda exc: "overridden by the user")
    explanation = whytrail.why(_s3_error())
    assert "overridden by the user" in explanation.text
