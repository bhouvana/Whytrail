"""Validates whytrail-marshmallow against a real marshmallow
ValidationError, including a nested-schema case (messages can be
nested dicts, not just a flat dict of lists)."""

from __future__ import annotations

import pytest

marshmallow = pytest.importorskip("marshmallow")
pytest.importorskip("whytrail.integrations.marshmallow")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


class UserSchema(marshmallow.Schema):
    name = marshmallow.fields.Str(required=True)
    age = marshmallow.fields.Int(required=True)
    email = marshmallow.fields.Email(required=True)


class AddressSchema(marshmallow.Schema):
    city = marshmallow.fields.Str(required=True)


class OrderSchema(marshmallow.Schema):
    address = marshmallow.fields.Nested(AddressSchema, required=True)


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(marshmallow.ValidationError) is not None


def test_why_shows_one_step_per_failing_field():
    with pytest.raises(marshmallow.ValidationError) as excinfo:
        UserSchema().load({"name": "a", "age": "not a number", "email": "bad"})

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "2 field(s)" in explanation.text
    assert "field 'age'" in explanation.text
    assert "field 'email'" in explanation.text


def test_nested_schema_field_path_is_dotted():
    with pytest.raises(marshmallow.ValidationError) as excinfo:
        OrderSchema().load({"address": {}})

    explanation = whytrail.why(excinfo.value)
    assert "field 'address.city'" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(marshmallow.ValidationError, lambda exc: "overridden by the user")
    with pytest.raises(marshmallow.ValidationError) as excinfo:
        UserSchema().load({"age": "not a number"})

    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text


def test_valid_data_does_not_raise():
    result = UserSchema().load({"name": "Alice", "age": 30, "email": "alice@example.com"})
    assert result["name"] == "Alice"
