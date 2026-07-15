"""Enforces the ADR §09 performance claim: untracked code pays
(effectively) nothing. Not a smoke test -- these numbers are what the
README's performance claims should be pulled from.

Run standalone (excluded from the default `pytest` collection --
benchmarks measure wall time and don't belong in a routine CI gate the
same way correctness tests do):

    pytest benchmarks/ --benchmark-only
"""

from __future__ import annotations

import whytrail


def _baseline_call(x: int) -> int:
    return x * 2


@whytrail.tracked
def _tracked_call(x: int) -> int:
    return x * 2


def test_untracked_function_call_baseline(benchmark):
    benchmark(_baseline_call, 21)


def test_tracked_decorator_outside_any_trace_scope(benchmark):
    """@tracked with no active trace() scope is a no-op past a single
    contextvar lookup (ADR §09: "default off" is non-negotiable) --
    this is the path most real deployments spend most of their time
    in, and it should read close to the baseline, not the ~100x this
    benchmark caught before the no-active-scope case was fixed to
    short-circuit."""
    benchmark(_tracked_call, 21)


def test_tracked_decorator_inside_active_trace_scope(benchmark):
    """The cost when actually capturing -- this number, not the two
    above, is the one to quote as "the price of tracking a call.\""""
    with whytrail.trace():
        benchmark(_tracked_call, 21)


def test_why_on_untracked_object(benchmark):
    benchmark(whytrail.why, 12345)


def test_why_on_exception():
    # not a hot path claim (exceptions are inherently expensive in
    # CPython already) -- included for completeness, not benchmarked
    # against a baseline.
    try:
        raise ValueError("x")
    except ValueError as exc:
        whytrail.why(exc)
