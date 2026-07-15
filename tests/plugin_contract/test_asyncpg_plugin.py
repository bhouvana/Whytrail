"""Validates whytrail-asyncpg against real asyncpg exception objects.

No live PostgreSQL connection needed or attempted: asyncpg's exception
attributes (sqlstate, detail, table_name, ...) are plain, settable
Python attributes -- unlike psycopg2's C-extension member descriptors,
which are genuinely read-only outside a real connection (see
docs/adr/0003-ecosystem-scale-triage.md's note on why psycopg2 itself
was deferred rather than tested this way)."""

from __future__ import annotations

import pytest

asyncpg = pytest.importorskip("asyncpg")
pytest.importorskip("whytrail.integrations.asyncpg")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


def _unique_violation(detail=None):
    err = asyncpg.UniqueViolationError('duplicate key value violates unique constraint "users_email_key"')
    err.sqlstate = "23505"
    err.table_name = "users"
    err.column_name = None
    err.constraint_name = "users_email_key"
    err.detail = detail if detail is not None else "Key (email)=(a@example.com) already exists."
    return err


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(asyncpg.PostgresError) is not None


def test_why_resolves_via_base_class_for_specific_subclass():
    exc = _unique_violation()
    assert type(exc).__name__ == "UniqueViolationError"
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "23505" in explanation.text
    assert "users_email_key" in explanation.text


def test_detail_is_in_locals_not_baked_into_description():
    exc = _unique_violation(detail="Key (email)=(secret@example.com) already exists.")
    explanation = whytrail.why(exc)
    detail_step = next(s for s in explanation.steps if s.locals)
    assert "secret@example.com" in detail_step.locals["detail"]
    assert "secret@example.com" not in detail_step.description


def test_redacted_hides_detail_but_keeps_constraint_name():
    exc = _unique_violation(detail="Key (email)=(secret@example.com) already exists.")
    explanation = whytrail.why(exc).redacted()
    assert "secret@example.com" not in explanation.text
    assert "users_email_key" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(asyncpg.PostgresError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_unique_violation())
    assert "overridden by the user" in explanation.text
