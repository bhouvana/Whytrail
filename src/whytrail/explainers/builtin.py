"""Tier 1: exception explanation (ADR §01, §02).

Reconstructs a causal chain entirely from data CPython already
retains -- __traceback__, __cause__, __context__, and (for as long as
something keeps the traceback alive) the locals of the frame where the
exception actually originated. No tracing engine, no opt-in, and it
works on any exception whytrail has never seen before -- this is the
"almost free" tier the rest of the library builds on top of.
"""

from __future__ import annotations

import types
import typing as t

from .._repr import safe_repr
from ..core.explanation import Explanation, ExplanationStep
from ..core.node import Confidence

MAX_LOCALS = 8
MAX_GROUP_EXCEPTIONS = 5

_RELATION_PHRASE = {
    "explicit": "which explicitly caused",
    "implicit": "during the handling of which",
}
_RELATION_CONFIDENCE = {
    "explicit": Confidence.EXPLICIT.value,
    "implicit": Confidence.INFERRED.value,
}


def explain_exception(exc: BaseException, *, max_depth: int = 8) -> Explanation:
    items, relations = _causal_chain(exc, max_depth=max_depth)
    steps: list[ExplanationStep] = []
    for i, item in enumerate(items):
        if i == 0:
            steps.extend(_steps_for(item, Confidence.EXPLICIT.value, max_depth=max_depth))
        else:
            relation = relations[i - 1]
            steps.extend(
                _steps_for(
                    item,
                    _RELATION_CONFIDENCE[relation],
                    connective=_RELATION_PHRASE[relation],
                    max_depth=max_depth,
                )
            )
    subject = f"{type(exc).__name__}: {exc}"
    return Explanation(subject=subject, steps=steps, tracked=True)


def _steps_for(
    exc: BaseException,
    confidence: float,
    connective: str | None = None,
    *,
    max_depth: int = 8,
    _depth: int = 0,
) -> list[ExplanationStep]:
    """Usually one step; more for a BaseExceptionGroup (Python 3.11+,
    what asyncio.TaskGroup and friends raise for structured concurrent
    failures). A group's whole point is bundling multiple *independent*
    failures into one exception -- showing only the group's own generic
    "N sub-exceptions" message and stopping there (which is what this
    function did before this fix) hides exactly the information anyone
    catching one of these actually wants. `.exceptions` is duck-typed
    via getattr rather than an isinstance check against
    (Base)ExceptionGroup, which doesn't exist as a name before 3.11 --
    same pattern as MONITORING_AVAILABLE's hasattr check elsewhere in
    this codebase for another 3.12-only feature."""
    step = _step_for(exc, confidence, connective=connective)
    sub_exceptions = getattr(exc, "exceptions", None)
    if not sub_exceptions or _depth >= max_depth:
        return [step]
    steps = [step]
    total = len(sub_exceptions)
    for i, sub in enumerate(sub_exceptions[:MAX_GROUP_EXCEPTIONS], start=1):
        steps.extend(
            _steps_for(
                sub,
                Confidence.EXPLICIT.value,
                connective=f"sub-exception {i} of {total}:",
                max_depth=max_depth,
                _depth=_depth + 1,
            )
        )
    if total > MAX_GROUP_EXCEPTIONS:
        steps.append(
            ExplanationStep(
                description=f"...and {total - MAX_GROUP_EXCEPTIONS} more sub-exception(s) not shown",
                confidence=Confidence.EXPLICIT.value,
                kind="exception",
            )
        )
    return steps


def _causal_chain(
    exc: BaseException, *, max_depth: int
) -> tuple[list[BaseException], list[str]]:
    """Return (items, relations): items oldest-first ending with exc
    itself; relations[i] describes the link items[i] -> items[i+1], one
    of "explicit" (__cause__, i.e. `raise ... from ...`) or "implicit"
    (__context__, chained automatically during exception handling,
    unless suppressed with `raise ... from None`)."""
    items: list[BaseException] = [exc]
    seen = {id(exc)}
    current = exc
    while len(items) < max_depth:
        if current.__cause__ is not None:
            nxt: BaseException | None = current.__cause__
            relation = "explicit"
        elif current.__context__ is not None and not current.__suppress_context__:
            nxt = current.__context__
            relation = "implicit"
        else:
            break
        if nxt is None or id(nxt) in seen:
            break
        items.append(nxt)
        seen.add(id(nxt))
        current = nxt
    items.reverse()
    relations = []
    for older, newer in zip(items, items[1:]):
        relations.append("explicit" if newer.__cause__ is older else "implicit")
    return items, relations


def _step_for(exc: BaseException, confidence: float, connective: str | None = None) -> ExplanationStep:
    frame, lineno = _origin_frame(exc)
    location = None
    locals_ = None
    if frame is not None:
        location = f"{frame.f_code.co_filename}:{lineno}, in {frame.f_code.co_name}"
        locals_ = _summarize_locals(frame)

    description = f"{type(exc).__name__}: {exc}"
    if connective:
        description = f"{connective} {description}"

    return ExplanationStep(
        description=description, confidence=confidence, location=location, kind="exception", locals=locals_
    )


def _origin_frame(exc: BaseException) -> tuple[types.FrameType | None, int | None]:
    """The innermost frame -- where the exception actually originated,
    not the outermost one where it was ultimately caught."""
    tb = exc.__traceback__
    if tb is None:
        return None, None
    while tb.tb_next is not None:
        tb = tb.tb_next
    return tb.tb_frame, tb.tb_lineno


def _summarize_locals(frame: types.FrameType) -> dict[str, str] | None:
    """A separate field from the description, deliberately (ADR 0002
    §3 item 5): a local variable at an exception's origin frame can
    hold a secret, and anything exporting an Explanation off-box needs
    to be able to drop this without parsing it out of prose text --
    see Explanation.redacted()."""
    candidates = [(name, value) for name, value in frame.f_locals.items() if not name.startswith("__")]
    locals_ = {name: safe_repr(value) for name, value in candidates[:MAX_LOCALS]}
    if len(candidates) > MAX_LOCALS:
        # ASCII "...", not the single ellipsis glyph -- the whole reason
        # confidence markers were switched to == / ~~ / .. earlier was a
        # cp1252 UnicodeEncodeError crashing this library's own output
        # on a default Windows console. Don't reintroduce that here.
        locals_["..."] = f"{len(candidates) - MAX_LOCALS} more not shown"
    return locals_ or None
