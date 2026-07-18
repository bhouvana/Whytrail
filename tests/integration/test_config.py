from __future__ import annotations

import pytest

import whytrail
from whytrail.config import ConfigError, env, load_dotenv


def test_env_outside_trace_scope_is_a_no_op_for_provenance(monkeypatch):
    """Same "off by default" contract as track() (ADR §09): the value
    still resolves correctly, but nothing is recorded outside a
    trace() scope."""
    monkeypatch.setenv("WHYTRAIL_TEST_KEY", "hello")
    value = env("WHYTRAIL_TEST_KEY")
    assert value == "hello"
    assert whytrail.why(value).known is False


def test_env_found_in_process_environment(monkeypatch):
    monkeypatch.setenv("WHYTRAIL_TEST_KEY", "hello")
    with whytrail.trace():
        value = env("WHYTRAIL_TEST_KEY")
    assert value == "hello"
    explanation = whytrail.why(value)
    assert explanation.known
    assert "environment variable 'WHYTRAIL_TEST_KEY'" in explanation.text


def test_env_falls_back_to_dotenv_mapping(monkeypatch):
    monkeypatch.delenv("WHYTRAIL_TEST_KEY", raising=False)
    with whytrail.trace():
        value = env("WHYTRAIL_TEST_KEY", dotenv={"WHYTRAIL_TEST_KEY": "from-dotenv"})
    assert value == "from-dotenv"
    explanation = whytrail.why(value)
    assert "from .env" in explanation.text


def test_env_var_wins_over_dotenv_when_both_present(monkeypatch):
    monkeypatch.setenv("WHYTRAIL_TEST_KEY", "from-env")
    with whytrail.trace():
        value = env("WHYTRAIL_TEST_KEY", dotenv={"WHYTRAIL_TEST_KEY": "from-dotenv"})
    assert value == "from-env"


def test_env_falls_back_to_default(monkeypatch):
    monkeypatch.delenv("WHYTRAIL_TEST_KEY", raising=False)
    with whytrail.trace():
        value = env("WHYTRAIL_TEST_KEY", "fallback")
    assert value == "fallback"
    explanation = whytrail.why(value)
    assert "default value for 'WHYTRAIL_TEST_KEY'" in explanation.text
    assert "not found" in explanation.text


def test_env_raises_config_error_with_no_default(monkeypatch):
    monkeypatch.delenv("WHYTRAIL_TEST_KEY", raising=False)
    with pytest.raises(ConfigError, match="WHYTRAIL_TEST_KEY"):
        env("WHYTRAIL_TEST_KEY")


def test_missing_key_error_is_explainable_through_tier_1(monkeypatch):
    """ConfigError needs no dedicated explainer -- it's a raised
    exception, so Tier 1 already covers it (ADR 0001)."""
    monkeypatch.delenv("WHYTRAIL_TEST_KEY", raising=False)
    try:
        env("WHYTRAIL_TEST_KEY", dotenv={})
    except ConfigError as exc:
        caught = exc
    explanation = whytrail.why(caught)
    assert "checked the environment, .env" in explanation.text


def test_cast_applies_only_to_a_found_raw_value(monkeypatch):
    monkeypatch.setenv("WHYTRAIL_TEST_KEY", "30")
    assert env("WHYTRAIL_TEST_KEY", cast=int) == 30

    monkeypatch.delenv("WHYTRAIL_TEST_KEY", raising=False)
    # default is returned as-is, never passed through cast
    assert env("WHYTRAIL_TEST_KEY", 30, cast=int) == 30


def test_load_dotenv_parses_a_simple_file(tmp_path):
    dotenv_file = tmp_path / ".env"
    dotenv_file.write_text(
        "\n".join(
            [
                "# a comment",
                "",
                "API_KEY=abc123",
                'QUOTED="has spaces"',
                "SINGLE_QUOTED='value'",
                "not a valid line",
            ]
        ),
        encoding="utf-8",
    )
    values = load_dotenv(str(dotenv_file))
    assert values == {
        "API_KEY": "abc123",
        "QUOTED": "has spaces",
        "SINGLE_QUOTED": "value",
    }
