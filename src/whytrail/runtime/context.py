"""contextvars-based scope propagation (ADR §04, §08).

contextvars is the only primitive that correctly follows a coroutine
across await points and thread handoffs without cross-talk between
concurrent tasks -- threading.local does not. Everything about "what
trace scope am I in right now" is built on top of it.
"""

from __future__ import annotations

import contextvars
import random
import typing as t

from ..core.graph import ProvenanceGraph

_current_scope: contextvars.ContextVar["TraceScope | None"] = contextvars.ContextVar(
    "whytrail_scope", default=None
)

# track()/@tracked are no-ops outside any open trace() scope (ADR §09:
# "default off" is non-negotiable, verified in benchmarks/test_overhead.py
# -- an early version of this let @tracked functions fully instrument on
# every call forever, unscoped, at ~100x baseline cost). This graph is
# the *destination* capture writes to once a scope decides capture is
# happening -- trace() defaults to it so `track(...)` inside a `with
# trace():` block stays queryable after the block exits without the
# caller having to save `as scope`.
_default_graph = ProvenanceGraph()


class TraceScope:
    """Scopes provenance capture to a block or a function (ADR §05, §09)."""

    def __init__(
        self,
        *,
        graph: ProvenanceGraph | None = None,
        sample_rate: float = 1.0,
        max_depth: int = 8,
        deep: bool = False,
    ) -> None:
        if not 0.0 <= sample_rate <= 1.0:
            raise ValueError("sample_rate must be within [0.0, 1.0]")
        if deep:
            from .monitoring import deep_trace_supported

            if not deep_trace_supported():
                raise RuntimeError(
                    "trace(deep=True) needs sys.monitoring (PEP 669), which requires "
                    "Python 3.12+; fall back to track()/@tracked on this interpreter."
                )
        # Defaults to the shared process-lifetime graph, not a fresh one.
        # A fresh ProvenanceGraph() here would be unreachable the moment
        # the `with` block exits unless the caller saved `as scope` --
        # a why() call right after a `with trace():` block is the most
        # common pattern and must keep working without that.
        self.graph = graph if graph is not None else _default_graph
        self.sample_rate = sample_rate
        self.max_depth = max_depth
        self.deep = deep
        self._token: contextvars.Token["TraceScope | None"] | None = None
        self._deep_stack: dict[int, list[t.Any]] = {}

    def should_capture(self) -> bool:
        return self.sample_rate >= 1.0 or random.random() < self.sample_rate

    def __enter__(self) -> "TraceScope":
        self._token = _current_scope.set(self)
        if self.deep:
            from . import monitoring

            monitoring.activate()
        return self

    def __exit__(self, *exc_info: object) -> None:
        if self.deep:
            from . import monitoring

            monitoring.deactivate()
        if self._token is not None:
            _current_scope.reset(self._token)
            self._token = None


def trace(
    *,
    graph: ProvenanceGraph | None = None,
    sample_rate: float = 1.0,
    max_depth: int = 8,
    deep: bool = False,
) -> TraceScope:
    """Scope provenance capture to a block.

        with whytrail.trace():
            ...

        with whytrail.trace(deep=True):
            # auto-instruments every call in this block via
            # sys.monitoring (PEP 669) -- no @tracked needed.
            # Requires Python 3.12+. See runtime/monitoring.py for
            # the honest cost/limitation of this mode.
            ...

    Context-manager only, deliberately -- trace() used to also work as
    a decorator, which meant @trace(...) and @tracked were two
    similarly-spelled decorators with genuinely different meanings
    (one opens a capture scope per call, the other records a call as
    a graph node). That ambiguity cost more than the four characters
    `with` saves; see the strategy review's API audit. Mark a function
    for capture with @tracked; open a scope with `with trace():`.
    """
    return TraceScope(graph=graph, sample_rate=sample_rate, max_depth=max_depth, deep=deep)


def current_scope() -> TraceScope | None:
    return _current_scope.get()


def active_graph() -> ProvenanceGraph:
    """The graph capture should write to right now: the innermost open
    trace() scope's graph, or the shared default graph outside any scope."""
    scope = current_scope()
    return scope.graph if scope is not None else _default_graph


def default_graph() -> ProvenanceGraph:
    return _default_graph
