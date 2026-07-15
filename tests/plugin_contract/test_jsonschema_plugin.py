"""Validates whytrail-jsonschema against a real jsonschema
ValidationError -- and specifically that a known-sensitive value
embedded in jsonschema's own .message text does not survive into
description or leak past .redacted()."""

from __future__ import annotations

import pytest

jsonschema = pytest.importorskip("jsonschema")
pytest.importorskip("whytrail_jsonschema")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_VALUE = "secret@example.com is not a number"
SCHEMA = {"type": "object", "properties": {"age": {"type": "integer"}}, "required": ["age"]}


def _validation_error():
    with pytest.raises(jsonschema.ValidationError) as excinfo:
        jsonschema.validate({"age": SECRET_VALUE}, SCHEMA)
    return excinfo.value


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(jsonschema.ValidationError) is not None


def test_sanity_message_really_does_embed_the_value():
    exc = _validation_error()
    assert SECRET_VALUE in exc.message


def test_why_shows_path_and_validator():
    exc = _validation_error()
    explanation = whytrail.why(exc)
    assert explanation.known
    assert "age" in explanation.text
    assert "'type'" in explanation.text


def test_description_never_contains_the_value():
    exc = _validation_error()
    explanation = whytrail.why(exc)
    for step in explanation.steps:
        assert SECRET_VALUE not in step.description
    assert SECRET_VALUE not in explanation.subject


def test_redacted_fully_removes_the_value():
    exc = _validation_error()
    explanation = whytrail.why(exc).redacted()
    assert SECRET_VALUE not in explanation.text
    assert "age" in explanation.text


def test_unredacted_text_still_shows_it_for_local_dev():
    exc = _validation_error()
    explanation = whytrail.why(exc)
    assert SECRET_VALUE in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(jsonschema.ValidationError, lambda exc: "overridden by the user")
    explanation = whytrail.why(_validation_error())
    assert "overridden by the user" in explanation.text
