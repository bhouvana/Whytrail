"""Validates the psycopg (v3) integration against a real psycopg.Error
with a settable .sqlstate -- confirmed directly that this attribute,
unlike psycopg2's C-level .pgcode, is a plain Python attribute."""

from __future__ import annotations

import pytest

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("whytrail.integrations.psycopg")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_TABLE = "secret_customer_table"


def _real_error(message: str, sqlstate: str = "42P01") -> "psycopg.Error":
    exc = psycopg.errors.UndefinedTable(message)
    exc.sqlstate = sqlstate
    return exc


def test_plugin_is_discovered():
    assert registry.resolve_explainer(psycopg.Error) is not None


def test_why_on_undefined_table_shows_sqlstate():
    exc = _real_error("relation does not exist")
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "42P01" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = _real_error(f'relation "{SECRET_TABLE}" does not exist')
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_TABLE in message_step.locals["message"]
    assert SECRET_TABLE not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_TABLE not in redacted.text
    assert "42P01" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(psycopg.Error, lambda exc: "overridden by the user")
    exc = _real_error("x")
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
