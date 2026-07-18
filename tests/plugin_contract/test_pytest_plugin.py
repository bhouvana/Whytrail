"""Validates whytrail-pytest end to end via pytest's own `pytester`
fixture -- a real subprocess-free pytest run against the actual
installed entry point, not a mock of the hook."""

from __future__ import annotations

import pytest

pytest.importorskip("whytrail.integrations.pytest_plugin")


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


TRACKED_VALUE_FAILING_TEST = """
import whytrail

def test_price_calculation():
    with whytrail.trace():
        raw = whytrail.track({"price": "12.50"}, label="raw CSV row")
        price = whytrail.track(float(raw["price"]), derived_from=raw)
        assert price == 999
"""


def test_tracked_locals_at_the_failing_assertion_are_surfaced(pytester):
    """Tier 1 alone (what the section already showed before 0.3) only
    explains "AssertionError at this line" -- never where `price`
    itself came from. This is the actual gap whytrail-pytest had:
    fixed by surfacing each track()ed local's own why() alongside the
    exception explanation, not by building a second plugin."""
    pytester.makepyfile(TRACKED_VALUE_FAILING_TEST)
    result = pytester.runpytest()
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(["*'price' was separately track()ed*", "*raw CSV row*"])


def test_no_whytrail_flag_also_suppresses_tracked_locals_section(pytester):
    pytester.makepyfile(TRACKED_VALUE_FAILING_TEST)
    result = pytester.runpytest("--no-whytrail")
    result.assert_outcomes(failed=1)
    output = "\n".join(result.outlines)
    assert "was separately track()ed" not in output


def test_untracked_assertion_failure_has_no_tracked_locals_section(pytester):
    """The common case (nothing in the test used track()) must not
    grow a section that says nothing -- absence, not an empty
    "nothing was tracked" note, matching how why() itself stays silent
    rather than padding output for information it doesn't have."""
    pytester.makepyfile(FAILING_TEST)
    result = pytester.runpytest()
    output = "\n".join(result.outlines)
    assert "was separately track()ed" not in output
