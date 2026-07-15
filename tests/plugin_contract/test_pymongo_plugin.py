"""Validates whytrail-pymongo against real pymongo error objects -- and
specifically that a value known to be embedded in the driver's own
message text does not survive redaction, since pymongo bakes
.details into exc.args[0] at construction time (see the module
docstring in whytrail_pymongo for why this needed a different design
than every other DB-driver plugin in this ecosystem)."""

from __future__ import annotations

import pytest

pymongo = pytest.importorskip("pymongo")
pytest.importorskip("whytrail_pymongo")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_EMAIL = "secret@example.com"


def _duplicate_key_error():
    return pymongo.errors.OperationFailure(
        f"E11000 duplicate key error collection: test.users index: email_1 dup key: {{ email: \"{SECRET_EMAIL}\" }}",
        code=11000,
        details={"keyValue": {"email": SECRET_EMAIL}, "errmsg": f"dup key: {{ email: \"{SECRET_EMAIL}\" }}"},
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(pymongo.errors.PyMongoError) is not None


def test_why_shows_code():
    exc = _duplicate_key_error()
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "11000" in explanation.text


def test_secret_value_is_confirmed_present_in_raw_driver_str():
    """Sanity check on the premise: pymongo really does embed the
    value in str(exc), which is exactly why description can't use it."""
    exc = _duplicate_key_error()
    assert SECRET_EMAIL in str(exc)
    assert SECRET_EMAIL in exc.args[0]


def test_description_never_contains_the_secret_value():
    exc = _duplicate_key_error()
    explanation = whytrail.why(exc)
    for step in explanation.steps:
        assert SECRET_EMAIL not in step.description
    assert SECRET_EMAIL not in explanation.subject


def test_redacted_fully_removes_the_secret_value():
    exc = _duplicate_key_error()
    explanation = whytrail.why(exc).redacted()
    assert SECRET_EMAIL not in explanation.text
    assert "11000" in explanation.text  # code survives redaction


def test_unredacted_text_still_contains_it_for_local_dev():
    exc = _duplicate_key_error()
    explanation = whytrail.why(exc)
    assert SECRET_EMAIL in explanation.text  # via locals, full detail for local dev


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pymongo.errors.PyMongoError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_duplicate_key_error())
    assert "overridden by the user" in explanation.text
