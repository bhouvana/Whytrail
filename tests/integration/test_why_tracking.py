from __future__ import annotations

import asyncio

import whytrail


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


def test_tracked_decorator_on_async_function_captures_the_awaited_result():
    """Regression test for a real 0.3 bug: calling an async @tracked
    function returns a coroutine immediately, so the old sync-only
    wrapper tracked the coroutine object (never the awaited value) --
    why() on the real result came back honestly-but-wrongly 'unknown'.
    """

    @whytrail.tracked
    async def double(x):
        await asyncio.sleep(0)
        return x * 2

    async def run():
        with whytrail.trace():
            return await double(21)

    result = asyncio.run(run())
    assert result == 42

    explanation = whytrail.why(result)
    assert explanation.known
    descriptions = " ".join(step.description for step in explanation.steps)
    assert "double(...)" in descriptions


def test_tracked_decorator_on_async_function_links_arguments_to_raised_exception():
    """The exception-linking branch was dead code for async functions
    before the fix: calling a coroutine function doesn't run its body,
    so the old wrapper's try/except around fn(*args, **kwargs) could
    never observe an exception raised inside an async def."""

    @whytrail.tracked
    async def explode(x):
        await asyncio.sleep(0)
        raise ValueError(f"bad input: {x}")

    async def run():
        with whytrail.trace():
            try:
                await explode(99)
            except ValueError as exc:
                return exc

    caught = asyncio.run(run())
    explanation = whytrail.why(caught)
    assert "bad input: 99" in explanation.text


def test_tracked_decorator_on_async_function_outside_trace_scope_is_a_no_op():
    calls = []

    @whytrail.tracked
    async def double(x):
        calls.append(x)
        return x * 2

    result = asyncio.run(double(21))
    assert result == 42
    assert calls == [21]  # the function still ran normally
    explanation = whytrail.why(result)
    assert explanation.known is False  # but nothing was captured


def test_tracked_decorator_on_generator_function_tracks_each_yielded_value():
    """Regression test for the same class of 0.3 bug as the async
    case: calling a generator function returns a generator object
    immediately, so the old wrapper tracked the generator itself, not
    the values it yields -- why() on a real yielded value came back
    'unknown'."""

    @whytrail.tracked
    def double_each(items):
        for item in items:
            yield item * 2

    with whytrail.trace():
        results = list(double_each([1, 2, 3]))

    assert results == [2, 4, 6]
    explanation = whytrail.why(results[1])
    assert explanation.known
    descriptions = " ".join(step.description for step in explanation.steps)
    assert "double_each(...)" in descriptions


def test_tracked_decorator_on_generator_function_links_arguments_to_raised_exception():
    @whytrail.tracked
    def gen_fails(n):
        for i in range(n):
            if i == 2:
                raise ValueError(f"bad item {i}")
            yield i

    with whytrail.trace():
        collected = []
        try:
            for x in gen_fails(5):
                collected.append(x)
        except ValueError as exc:
            caught = exc

    assert collected == [0, 1]  # partial iteration before the raise
    explanation = whytrail.why(caught)
    assert "bad item 2" in explanation.text


def test_tracked_decorator_on_generator_function_outside_trace_scope_is_a_no_op():
    calls = []

    @whytrail.tracked
    def gen():
        calls.append("ran")
        yield [999001]  # a list, not a small cached int, for a reliable identity check
        yield [999002]

    results = list(gen())
    assert calls == ["ran"]  # the generator still ran normally
    assert whytrail.why(results[0]).known is False  # but nothing was captured


def test_tracked_decorator_on_async_generator_function_tracks_each_yielded_value():
    @whytrail.tracked
    async def double_each(items):
        for item in items:
            await asyncio.sleep(0)
            yield item * 2

    async def run():
        with whytrail.trace():
            return [x async for x in double_each([1, 2, 3])]

    results = asyncio.run(run())
    assert results == [2, 4, 6]
    explanation = whytrail.why(results[1])
    assert explanation.known
    descriptions = " ".join(step.description for step in explanation.steps)
    assert "double_each(...)" in descriptions


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
