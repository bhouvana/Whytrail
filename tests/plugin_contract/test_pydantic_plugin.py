"""Validates whytrail-pydantic against a real pydantic ValidationError,
not a constructed mock."""

from __future__ import annotations

import pytest

pydantic = pytest.importorskip("pydantic")
pytest.importorskip("whytrail_pydantic")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402


class User(pydantic.BaseModel):
    name: str
    age: int
    email: str = pydantic.Field(pattern=r"^[^@]+@[^@]+$")


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(pydantic.ValidationError) is not None


def test_why_shows_one_step_per_failing_field():
    with pytest.raises(pydantic.ValidationError) as excinfo:
        User(name="a", age="not a number", email="bad")

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert "2 validation error" in explanation.text
    assert "field 'age'" in explanation.text
    assert "field 'email'" in explanation.text


def test_bad_input_values_are_in_locals_not_description():
    with pytest.raises(pydantic.ValidationError) as excinfo:
        User(name="a", age="not a number", email="bad")

    explanation = whytrail.why(excinfo.value)
    age_step = next(s for s in explanation.steps if "age" in s.description)
    assert age_step.locals is not None
    assert "not a number" not in age_step.description
    assert "not a number" in age_step.locals["input"]


def test_redacted_hides_bad_values_but_keeps_field_names():
    with pytest.raises(pydantic.ValidationError) as excinfo:
        User(name="a", age="not a number", email="bad")

    explanation = whytrail.why(excinfo.value).redacted()
    assert "not a number" not in explanation.text
    assert "field 'age'" in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(pydantic.ValidationError, lambda exc: "overridden by the user")
    with pytest.raises(pydantic.ValidationError) as excinfo:
        User(name="a", age="not a number", email="bad")

    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text


def test_single_field_valid_model_does_not_raise():
    user = User(name="Alice", age=30, email="alice@example.com")
    assert user.name == "Alice"
