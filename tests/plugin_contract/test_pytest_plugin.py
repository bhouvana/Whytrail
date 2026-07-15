"""Validates whytrail-pytest end to end via pytest's own `pytester`
fixture -- a real subprocess-free pytest run against the actual
installed entry point, not a mock of the hook."""

from __future__ import annotations

import pytest

pytest.importorskip("whytrail_pytest")


FAILING_TEST = """
def load_codes(region):
    table = {}
    if region not in table:
        raise ValueError(f"missing region {region!r}")
    return table

def test_something():
    try:
        load_codes("EU")
    except ValueError as exc:
        raise KeyError("SUMMER") from exc
"""

PASSING_TEST = """
def test_ok():
    assert 1 + 1 == 2
"""


def test_plugin_is_auto_registered(pytester):
    pytester.makepyfile(PASSING_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(passed=1)


def test_whytrail_section_appears_on_failure(pytester):
    pytester.makepyfile(FAILING_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*whytrail*", "*which explicitly caused KeyError*"])


def test_no_whytrail_flag_suppresses_the_section(pytester):
    pytester.makepyfile(FAILING_TEST)
    result = pytester.runpytest("--no-whytrail")
    result.assert_outcomes(failed=1)
    output = "\n".join(result.outlines)
    assert "----------------------------------- whytrail" not in output
    assert "which explicitly caused KeyError" not in output


def test_whytrail_graph_flag_includes_mermaid(pytester):
    pytester.makepyfile(FAILING_TEST)
    result = pytester.runpytest("--whytrail-graph")
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*graph TD*"])


def test_passing_tests_have_no_whytrail_section(pytester):
    """A passing run still legitimately mentions "whytrail" once, in
    pytest's own plugin-registration banner (`plugins: whytrail-pytest-
    ...`) -- that's pytest announcing what's installed, not our
    plugin adding a section. What must never appear is the section
    marker itself."""
    pytester.makepyfile(PASSING_TEST)
    result = pytester.runpytest()
    output = "\n".join(result.outlines)
    assert "----------------------------------- whytrail" not in output
