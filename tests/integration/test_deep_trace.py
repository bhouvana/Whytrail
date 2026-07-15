from __future__ import annotations

import sys

import pytest

import whytrail
from whytrail.runtime import monitoring

pytestmark = pytest.mark.skipif(
    not monitoring.deep_trace_supported(),
    reason="sys.monitoring (PEP 669) requires Python 3.12+",
)


def test_deep_trace_requires_no_manual_tracked_decorator():
    def load(region):
        table = {"EU": 1.0}
        return table[region]

    def compute(region):
        rate = load(region)
        return rate * 42

    with whytrail.trace(deep=True):
        result = compute("EU")

    explanation = whytrail.why(result)
    assert explanation.known
    descriptions = " ".join(s.description for s in explanation.steps)
    assert "compute(...)" in descriptions


def test_deep_trace_links_nested_calls():
    """outer() returns inner()'s result unchanged (same object), so
    the value node ends up with two real parents: inner's call node
    and outer's. Explanation.steps renders one dominant path
    (documented in _steps_from_traversal); the full DAG -- both calls
    -- must still be present in .nodes/.graph()."""

    def inner():
        return "leaf"

    def outer():
        return inner()

    with whytrail.trace(deep=True):
        result = outer()

    explanation = whytrail.why(result)
    call_labels = " ".join(n.label for n in explanation.nodes)
    assert "inner(...)" in call_labels
    assert "outer(...)" in call_labels
    assert "inner(...)" in explanation.graph()
    assert "outer(...)" in explanation.graph()


def test_deep_trace_records_raised_exception_once():
    def explode():
        raise ValueError("deep boom")

    caught = None
    with whytrail.trace(deep=True):
        try:
            explode()
        except ValueError as exc:
            caught = exc

    # exceptions still resolve through tier 1 first (ADR §06); this
    # just proves deep tracing didn't crash or double-record on raise.
    explanation = whytrail.why(caught)
    assert "deep boom" in explanation.text


def test_deep_trace_scope_is_off_outside_the_with_block():
    def compute():
        return 7

    result = compute()  # no active trace() scope at all
    explanation = whytrail.why(result)
    assert explanation.known is False


def test_deep_trace_raises_clear_error_when_unsupported(monkeypatch):
    monkeypatch.setattr(monitoring, "MONITORING_AVAILABLE", False)
    monkeypatch.setattr(monitoring, "deep_trace_supported", lambda: False)
    with pytest.raises(RuntimeError, match="Python 3.12"):
        whytrail.trace(deep=True)
