"""Shared bounded, never-raising repr helper.

whytrail's core promise (ADR §19) is that it never raises from inside
its own machinery, even when the object being described has a broken
or hostile __repr__. Every place that needs a short label for an
arbitrary object goes through here.
"""

from __future__ import annotations

import reprlib
import typing as t

_repr = reprlib.Repr()
_repr.maxstring = 100
_repr.maxother = 100
_repr.maxlist = 8
_repr.maxdict = 8
_repr.maxtuple = 8
_repr.maxset = 8


def safe_repr(value: t.Any) -> str:
    # Belt-and-suspenders, confirmed by a negative test (test_negative_inputs.py):
    # reprlib.Repr already has its own internal fallback for an object
    # whose __repr__ raises (or infinitely recurses, itself a
    # RecursionError) -- repr_instance() catches it and returns
    # "<ClassName instance at 0x...>" before this except clause ever
    # sees it. This except still matters for anything reprlib's own
    # dispatch doesn't route through repr_instance() (e.g. a container
    # whose *contents* raise while reprlib is formatting them).
    try:
        return _repr.repr(value)
    except Exception:  # noqa: BLE001 - deliberately broad, see module docstring
        return f"<unrepresentable {type(value).__name__}>"
