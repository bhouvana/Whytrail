"""Object explainability protocol (ADR §07).

A __why__ dunder is the same shape as __repr__: opt-in, duck-typed, no
metaclass or ABC registration required. A class that implements it can
describe its own provenance without a plugin package existing at all.

What's deliberately *not* here is a universal transparent proxy that
would make __why__ "just work" on every object automatically --
wrapping changes identity and type, which breaks isinstance checks and
fast paths in C-optimized libraries (NumPy ufuncs in particular). See
ADR §07 for the full reasoning.
"""

from __future__ import annotations

import typing as t

from ._repr import safe_repr
from .core.explanation import Explanation, ExplanationStep

WhyResult = t.Union[Explanation, str]


@t.runtime_checkable
class SupportsWhy(t.Protocol):
    def __why__(self) -> WhyResult: ...


def call_why_protocol(obj: t.Any) -> Explanation | None:
    """Returns None if obj has no __why__, or if __why__ raised --
    either way, resolution falls through to the next strategy (ADR
    §06) rather than propagating the failure to the caller."""
    method = getattr(type(obj), "__why__", None)
    if method is None:
        return None
    try:
        result = method(obj)
    except Exception:  # noqa: BLE001 - a hostile __why__ must not crash why()
        return None
    return _coerce(obj, result)


def _coerce(obj: t.Any, result: t.Any) -> Explanation | None:
    if isinstance(result, Explanation):
        return result
    if isinstance(result, str):
        return Explanation(subject=safe_repr(obj), steps=[ExplanationStep(description=result)], tracked=True)
    return None
