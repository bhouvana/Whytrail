"""Validates the graphql_core integration against a real
graphql.GraphQLError, the type underneath strawberry-graphql, Ariadne,
and graphene."""

from __future__ import annotations

import pytest

graphql = pytest.importorskip("graphql")
pytest.importorskip("whytrail.integrations.graphql_core")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_VALUE = "secret_internal_value_xyz"


def test_plugin_is_discovered():
    assert registry.resolve_explainer(graphql.GraphQLError) is not None


def test_why_on_graphql_error_shows_path():
    exc = graphql.GraphQLError("resolver failed", path=["user", "profile", "ssn"])
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "user" in explanation.text and "ssn" in explanation.text


def test_message_is_in_locals_and_strippable_via_redacted():
    exc = graphql.GraphQLError(f"resolver failed: {SECRET_VALUE}", path=["user"])
    explanation = whytrail.why(exc)
    message_step = next(s for s in explanation.steps if s.locals)
    assert SECRET_VALUE in message_step.locals["message"]
    assert SECRET_VALUE not in message_step.description

    redacted = explanation.redacted()
    assert SECRET_VALUE not in redacted.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(graphql.GraphQLError, lambda exc: "overridden by the user")
    exc = graphql.GraphQLError("x", path=["user"])
    explanation = whytrail.why(exc)
    assert "overridden by the user" in explanation.text
