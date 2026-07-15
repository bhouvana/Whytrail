from __future__ import annotations

import whytrail
from whytrail.core.node import Confidence


def test_untracked_value_is_honestly_unknown():
    explanation = whytrail.why(12345)
    assert explanation.known is False
    assert explanation.tracked is False


def test_track_outside_any_trace_scope_is_a_no_op():
    """ADR §09: capture is off by default, non-negotiable. track()
    called with no open trace() scope must not write to the shared
    graph at all -- otherwise a value tracked once at import time (or
    a @tracked-decorated hot-path function, see the next test) would
    silently accumulate in the default graph forever, unscoped."""
    value = whytrail.track([1, 2, 3], label="should not be captured")
    explanation = whytrail.why(value)
    assert explanation.known is False


def test_tracked_decorator_outside_any_trace_scope_is_a_no_op():
    calls = []

    @whytrail.tracked
    def double(x):
        calls.append(x)
        return x * 2

    result = double(21)
    assert result == 42
    assert calls == [21]  # the function still ran normally
    explanation = whytrail.why(result)
    assert explanation.known is False  # but nothing was captured


def test_track_makes_a_value_explainable():
    with whytrail.trace():
        value = whytrail.track({"x": 1}, label="tracked dict")
    explanation = whytrail.why(value)
    assert explanation.known
    assert "tracked dict" in explanation.text


def test_track_survives_past_the_with_block():
    """The most common pattern: track inside `with trace():`, ask why()
    right after the block exits without ever saving `as scope`."""
    with whytrail.trace():
        value = whytrail.track([1, 2, 3], label="a list")
    explanation = whytrail.why(value)
    assert explanation.known


def test_derived_from_builds_a_causal_chain():
    with whytrail.trace():
        raw = whytrail.track("12.5", label="raw string")
        price = whytrail.track(12.5, derived_from=raw, label="parsed price")
    explanation = whytrail.why(price)
    descriptions = " ".join(step.description for step in explanation.steps)
    assert "raw string" in descriptions
    assert "parsed price" in descriptions
    # root cause (raw) should come before the derived value in the chain
    raw_index = next(i for i, s in enumerate(explanation.steps) if "raw string" in s.description)
    price_index = next(i for i, s in enumerate(explanation.steps) if "parsed price" in s.description)
    assert raw_index < price_index


def test_tracked_decorator_links_arguments_to_return_value():
    @whytrail.tracked
    def double(x):
        return x * 2

    with whytrail.trace():
        result = double(21)

    explanation = whytrail.why(result)
    descriptions = " ".join(step.description for step in explanation.steps)
    assert "double(...)" in descriptions


def test_tracked_decorator_links_arguments_to_raised_exception():
    @whytrail.tracked
    def explode(x):
        raise ValueError(f"bad input: {x}")

    with whytrail.trace():
        try:
            explode(99)
        except ValueError as exc:
            caught = exc

    # exceptions always resolve through tier 1 first (ADR §06 order),
    # which is correct even though this exception also has a graph node
    explanation = whytrail.why(caught)
    assert "bad input: 99" in explanation.text


def test_trace_sample_rate_zero_disables_capture():
    with whytrail.trace(sample_rate=0.0):
        value = whytrail.track([1], label="should not be captured")
    explanation = whytrail.why(value)
    assert explanation.known is False


def test_trace_scope_is_reentrant_across_recursive_calls():
    calls = []

    def recurse(n):
        with whytrail.trace(sample_rate=1.0):
            calls.append(n)
            if n == 0:
                return 0
            return recurse(n - 1)

    assert recurse(3) == 0
    assert calls == [3, 2, 1, 0]
