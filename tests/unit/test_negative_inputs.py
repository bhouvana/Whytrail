"""Negative testing and API invariants: pathological objects that
should never crash `why()`/`track()`, and the contract every caller of
`why()` can rely on regardless of input.

Scoped to concrete, plausible failure points already present in the
code, not a generic "throw random garbage at everything" fuzzer:
`track()`'s default label calls `repr()` on the tracked object
(`runtime/capture.py`), and Tier 1 walks `__cause__`/`__context__`
chains (`explainers/builtin.py`) -- both are real places a hostile or
merely unlucky object could break things if the existing guards
(`safe_repr`'s broad except, `_causal_chain`'s `seen` set) didn't
actually work. Confirmed here rather than assumed from reading the
code.
"""

from __future__ import annotations

import sys

import pytest

import whytrail
from whytrail._repr import safe_repr


class _RaisingRepr:
    def __repr__(self) -> str:
        raise RuntimeError("__repr__ itself is broken")


class _InfinitelyRecursiveRepr:
    def __repr__(self) -> str:
        return repr(self)  # calls itself forever, not a base case bug -- deliberate


class _RaisingEq:
    def __eq__(self, other: object) -> bool:
        raise RuntimeError("__eq__ itself is broken")

    def __hash__(self) -> int:
        raise RuntimeError("__hash__ itself is broken")


class _RaisingGetattr:
    def __getattr__(self, name: str):
        raise RuntimeError(f"__getattr__ itself is broken for {name!r}")


# -- repr()-raising / infinitely-recursive objects ----------------------


def test_safe_repr_survives_a_raising_repr():
    # Real finding, not assumed: reprlib.Repr has its *own* internal
    # fallback for a raising __repr__ (repr_instance() catches the
    # exception and returns "<ClassName instance at 0x...>" itself,
    # before it ever reaches safe_repr's own try/except) -- so
    # safe_repr's "<unrepresentable ...>" branch never actually fires
    # for this case; reprlib's own safety net does. Both are safe
    # outcomes (neither raises), so this checks for either rather than
    # assuming which layer handles it.
    result = safe_repr(_RaisingRepr())
    assert "unrepresentable" in result or "instance at" in result


def test_safe_repr_survives_infinite_repr_recursion():
    # Same finding as above: reprlib's repr_instance() catches
    # RecursionError internally too (RecursionError is a RuntimeError
    # subclass) before safe_repr's own except ever sees it.
    result = safe_repr(_InfinitelyRecursiveRepr())
    assert "unrepresentable" in result or "instance at" in result


def test_track_survives_a_raising_repr_object():
    with whytrail.trace():
        obj = whytrail.track(_RaisingRepr())
        explanation = whytrail.why(obj)
    assert explanation.known
    assert isinstance(explanation, whytrail.Explanation)


def test_why_survives_a_raising_repr_object_even_untracked():
    explanation = whytrail.why(_RaisingRepr())
    assert isinstance(explanation, whytrail.Explanation)
    assert explanation.known is False


def test_why_survives_an_object_with_raising_eq_and_hash():
    # track()/why() key by id(obj), never hash()/== -- confirmed here,
    # not assumed, since a broken __eq__/__hash__ would otherwise be
    # exactly the kind of thing a dict-based registry could crash on.
    with whytrail.trace():
        obj = whytrail.track(_RaisingEq())
        explanation = whytrail.why(obj)
    assert explanation.known


def test_why_survives_an_object_with_raising_getattr():
    explanation = whytrail.why(_RaisingGetattr())
    assert isinstance(explanation, whytrail.Explanation)


def test_recursive_container_repr_is_safe():
    # Built-in containers detect self-reference themselves (CPython's
    # Py_ReprEnter/Py_ReprLeave) -- confirmed this doesn't regress
    # through reprlib.Repr specifically, not assumed from "lists handle
    # this in general."
    cycle: list = []
    cycle.append(cycle)
    result = safe_repr(cycle)
    assert "..." in result or "unrepresentable" in result


# -- self-referential exception chains -----------------------------------


def test_why_on_a_self_referential_cause_terminates():
    exc = ValueError("boom")
    exc.__cause__ = exc  # pathological, but constructible after the fact
    explanation = whytrail.why(exc)
    assert isinstance(explanation, whytrail.Explanation)
    assert explanation.known
    # _causal_chain's `seen` set must have actually broken the cycle --
    # otherwise this call would never have returned at all.
    assert len(explanation.steps) >= 1


def test_why_on_a_two_cycle_of_causes_terminates():
    a = ValueError("a")
    b = ValueError("b")
    a.__cause__ = b
    b.__cause__ = a
    explanation = whytrail.why(a)
    assert isinstance(explanation, whytrail.Explanation)
    assert explanation.known


@pytest.mark.skipif(sys.version_info < (3, 11), reason="BaseExceptionGroup requires Python 3.11+")
def test_why_on_a_deeply_nested_exception_group_is_bounded():
    # True self-reference turned out to be unconstructable (real
    # finding, not assumed): BaseExceptionGroup.exceptions is a
    # read-only attribute -- assigning to it after construction raises
    # AttributeError, so a pathological instance can't be built the way
    # a first version of this test assumed. What *is* real and
    # constructible: a legitimately deep chain of nested groups (a
    # plausible shape for structured concurrency failures nested inside
    # each other), which exercises the same `_depth >= max_depth` bound
    # in explainers/builtin.py's `_steps_for` without needing a cycle.
    #
    # Missing this skipif guard entirely was a real bug, caught by
    # `ruff check` (F821: BaseExceptionGroup undefined) rather than by
    # actually running this suite on Python 3.10/3.11 -- this project's
    # own CI matrix includes both, but no CI job has ever executed for
    # real yet (see docs/testing-maturity.md), so this would have
    # failed with a bare NameError the first time it did, on a Python
    # version this project claims to support.
    innermost: BaseException = ValueError("root cause")
    for i in range(50):
        innermost = BaseExceptionGroup(f"level {i}", [innermost])  # noqa: F821
    explanation = whytrail.why(innermost)
    assert isinstance(explanation, whytrail.Explanation)
    # max_depth (default 8) bounds this rather than producing 50 steps
    # or blowing the stack -- confirmed by this call actually returning
    # quickly with a small step count, not by reading the code.
    assert len(explanation.steps) <= 10


# -- API invariant: why(obj) always returns an Explanation ---------------

def _generator():
    yield 1


class _CircularDict:
    """A __dict__ that references the instance itself -- distinct from
    the recursive-list case above (that's built-in-container self-
    reference; this is an arbitrary object graph cycle reachable via
    attribute access, the shape a real linked data structure or ORM
    model with a back-reference actually has)."""

    def __init__(self) -> None:
        self.self_ref = self


_circular = _CircularDict()

_PATHOLOGICAL_INPUTS = [
    None,
    _RaisingRepr(),
    _InfinitelyRecursiveRepr(),
    _RaisingEq(),
    _RaisingGetattr(),
    object(),
    (lambda: None),
    type,
    NotImplemented,
    _generator(),
    _circular,
    b"\xff\xfe not valid utf-8",
    float("nan"),
    float("inf"),
    {"a": {"b": {"c": object()}}},  # nested nothing-special container
]


def test_why_always_returns_an_explanation_never_raises():
    for obj in _PATHOLOGICAL_INPUTS:
        explanation = whytrail.why(obj)
        assert isinstance(explanation, whytrail.Explanation), f"why({obj!r}) returned {type(explanation)!r}"
        # .text/.json()/.redacted()/.graph() must themselves never raise
        # either -- why() returning an Explanation is only half the
        # contract if rendering it can still crash the caller.
        assert isinstance(explanation.text, str)
        assert isinstance(explanation.json(), dict)
        assert isinstance(explanation.redacted(), whytrail.Explanation)
        assert isinstance(explanation.graph(), str)
