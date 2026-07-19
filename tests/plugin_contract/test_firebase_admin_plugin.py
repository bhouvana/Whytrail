"""Validates whytrail's firebase-admin plugin against real
firebase_admin.exceptions.FirebaseError objects -- no live Firebase
project or credentials needed."""

from __future__ import annotations

import pytest

firebase_admin = pytest.importorskip("firebase_admin")
pytest.importorskip("whytrail.integrations.firebase_admin")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from firebase_admin.exceptions import FirebaseError, NotFoundError  # noqa: E402

SECRET_UID = "user-secret-uid-000111"


def _firebase_error(message=None, cause=None):
    return NotFoundError(message=message if message is not None else f"No user record found for uid: {SECRET_UID}", cause=cause)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(FirebaseError) is not None


def test_why_on_firebase_error_shows_code():
    explanation = whytrail.why(_firebase_error())
    assert explanation.known
    assert "NOT_FOUND" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_firebase_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_UID in detail_step.locals["message"]
    assert SECRET_UID not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_UID not in redacted.text
    assert "NOT_FOUND" in redacted.text


def test_cause_is_in_locals_when_present():
    cause = ValueError("underlying cause")
    explanation = whytrail.why(_firebase_error(cause=cause))
    detail_step = next(s for s in explanation.steps if s.locals)
    assert "underlying cause" in detail_step.locals["cause"]


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(FirebaseError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_firebase_error())
    assert "overridden by the user" in explanation.text
