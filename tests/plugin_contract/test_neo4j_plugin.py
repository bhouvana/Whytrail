"""Validates whytrail's neo4j plugin against real
neo4j.exceptions.Neo4jError objects, hydrated the same way the driver
hydrates them internally from a server response -- no live Neo4j
instance needed."""

from __future__ import annotations

import pytest

neo4j = pytest.importorskip("neo4j")
pytest.importorskip("whytrail.integrations.neo4j")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402
from neo4j.exceptions import Neo4jError  # noqa: E402

SECRET_VALUE = "email=secret@example.com"


def _neo4j_error(code="Neo.ClientError.Schema.ConstraintValidationFailed", message=None):
    return Neo4jError._hydrate_neo4j(
        code=code, message=message if message is not None else f"Node already exists with {SECRET_VALUE}"
    )


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(Neo4jError) is not None


def test_why_on_neo4j_error_shows_code_and_classification():
    explanation = whytrail.why(_neo4j_error())
    assert explanation.known
    assert "Neo.ClientError.Schema.ConstraintValidationFailed" in explanation.text
    assert "ClientError" in explanation.text
    assert "Schema" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    explanation = whytrail.why(_neo4j_error())
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_VALUE in message_step.locals["message"]
    assert SECRET_VALUE not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_VALUE not in redacted.text
    assert "ConstraintValidationFailed" in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(Neo4jError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_neo4j_error())
    assert "overridden by the user" in explanation.text
