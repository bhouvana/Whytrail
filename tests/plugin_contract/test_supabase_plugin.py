"""Validates whytrail's supabase plugin against a real
postgrest.exceptions.APIError -- the actual exception type
supabase-py's database calls raise (via its underlying PostgREST
client), confirmed by tracing what a real `.table(...)` call raises
rather than assumed. No live Supabase project needed."""

from __future__ import annotations

import pytest

supabase = pytest.importorskip("supabase")
postgrest = pytest.importorskip("postgrest")
pytest.importorskip("whytrail.integrations.supabase")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from postgrest.exceptions import APIError  # noqa: E402

SECRET_VALUE = "duplicate email secret@example.com"


def _api_error(details=None):
    return APIError(
        {
            "message": "duplicate key value violates unique constraint",
            "code": "23505",
            "hint": None,
            "details": details if details is not None else SECRET_VALUE,
        }
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(APIError) is not None


def test_why_on_api_error_shows_postgres_code():
    explanation = whytrail.why(_api_error())
    assert explanation.known
    assert "23505" in explanation.text


def test_details_are_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_api_error())
    detail_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_VALUE in detail_step.locals["details"]
    assert SECRET_VALUE not in detail_step.description

    redacted = explanation.redacted()
    assert SECRET_VALUE not in redacted.text
    assert "23505" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(APIError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_api_error())
    assert "overridden by the user" in explanation.text
