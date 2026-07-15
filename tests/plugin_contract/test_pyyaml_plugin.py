"""Validates whytrail-pyyaml against real yaml.MarkedYAMLError objects,
including the ConstructorError case that motivated keeping .problem
out of description (it embeds the actual tag string from the
document, discovered while building this plugin -- see the module
docstring in whytrail_pyyaml)."""

from __future__ import annotations

import pytest

yaml = pytest.importorskip("yaml")
pytest.importorskip("whytrail_pyyaml")

import whytrail  # noqa: E402
from whytrail import registry  # noqa: E402

SECRET_TAG = "secret_value_here"


def test_plugin_is_discovered_via_entry_point():
    assert registry.resolve_explainer(yaml.MarkedYAMLError) is not None


def test_why_on_parser_error_shows_location():
    with pytest.raises(yaml.YAMLError) as excinfo:
        yaml.safe_load("a: [1, 2\nb: 3")

    explanation = whytrail.why(excinfo.value)
    assert explanation.known
    assert ":2:" in explanation.text  # line 2


def test_constructor_error_tag_string_never_in_description():
    with pytest.raises(yaml.YAMLError) as excinfo:
        yaml.safe_load(f"a: !!python/object/{SECRET_TAG}")

    exc = excinfo.value
    assert isinstance(exc, yaml.constructor.ConstructorError)
    assert SECRET_TAG in exc.problem  # sanity: confirms the premise

    explanation = whytrail.why(exc)
    for step in explanation.steps:
        assert SECRET_TAG not in step.description
    assert SECRET_TAG not in explanation.subject


def test_redacted_fully_removes_the_tag_string():
    with pytest.raises(yaml.YAMLError) as excinfo:
        yaml.safe_load(f"a: !!python/object/{SECRET_TAG}")

    explanation = whytrail.why(excinfo.value).redacted()
    assert SECRET_TAG not in explanation.text


def test_unredacted_text_still_shows_problem_for_local_dev():
    with pytest.raises(yaml.YAMLError) as excinfo:
        yaml.safe_load(f"a: !!python/object/{SECRET_TAG}")

    explanation = whytrail.why(excinfo.value)
    assert SECRET_TAG in explanation.text


def test_manual_registration_still_overrides_the_plugin():
    whytrail.register(yaml.MarkedYAMLError, lambda exc: "overridden by the user")
    with pytest.raises(yaml.YAMLError) as excinfo:
        yaml.safe_load("a: [1, 2\nb: 3")

    explanation = whytrail.why(excinfo.value)
    assert "overridden by the user" in explanation.text
